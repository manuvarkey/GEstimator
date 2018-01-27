#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# schedule.py
#
#  Copyright 2014 Manu Varkey <manuvarkey@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import logging, copy, re
import peewee, sqlite3
from playhouse.migrate import migrate, SqliteMigrator
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP

# Rate rounding function with support for ro
def Currency(x, places=2):
    if int(places) == places:
        return Decimal(x).quantize(Decimal(str(10**(-places))), rounding=ROUND_HALF_UP)
    else:
        precision = int(places)
        base = int((places - int(places))*10)
        mod_x = Decimal(base/(10**precision))*Decimal(x*(10**precision)/base).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
        return Decimal(mod_x).quantize(Decimal(str(10**(-precision))), rounding=ROUND_HALF_UP)

# Local files import
from .. import misc, undo
from ..undo import undoable, group

# Get logger object
log = logging.getLogger()

# Module functions

def parse_analysis(models, item, index, set_code=False, settings=None):
    """Parses first instance of analysis of rates into item starting from index"""

    def string_has(string, values):
        """Check if string has one of the values in values"""
        string_formated = string.lower()
        for value in values:
            if value in string_formated:
                return True
        return False

    def search_for_values(models, indexes, cols, values=None):
        """Search up or down in model columns from index for value in list"""
        for index in indexes:
            if index >= 0:
                for col in cols:
                    if values is None:
                        if models[index][col] != '':
                            return [models[index][col], index, col]
                    elif string_has(models[index][col], values):
                        return [models[index][col], index, col]
        return None

    [UP, DOWN] = [0,1]
    [SEARCHING, ITEM, GROUP] = [0,1,2]
    RES_KEYS = ['material', 'labour','tool','plant','a1','a2','a3','a4','b1','b2','b3','b4']
    ANA_REMARK_KEYS = ['cost of','cost per','cost for', 'rate of','rate per','rate for', 'details of']
    SUM_KEYS = ['total', 'rate per', 'cost per', 'cost for', 'rate for', 'cost of', 'rate of']
    WEIGHT_KEYS = ['@','%']
    TIMES_KEYS = ['rate per', 'rate for', 'cost per', 'cost for','cost of', 'rate of']
    ROUND_KEYS = ['say']

    if settings:
        (comment_loc, round_val) = settings
    else:
        (comment_loc, round_val) = (DOWN, -1)
        
    # Initialise and start state machine
    
    state = SEARCHING
    item_start = 0
    group = None

    while index < len(models):
        model = models[index]
        # Search for item
        if state == SEARCHING:
            if 'description' in model[1].lower() and 'unit' in model[2].lower():
                code_query = search_for_values(models, range(index-1,index-5,-1), [0])

                if code_query:
                    state = ITEM
                    if set_code:
                        item.code = code_query[0]
                        item_code_index = code_query[1]
                    if index+2 < len(models):  # Hack to prevent failures in bad files
                        ana_query = search_for_values(models, range(item_code_index+1,index+2), [0,1,2], ANA_REMARK_KEYS)
                        if ana_query:
                            item.ana_remarks = ana_query[0]
                            if ana_query[1] > index:
                                index = ana_query[1]
            
                    item_start = index
            index = index + 1
            continue

        # Handle different classes of items
        elif state == ITEM:
            # If group add group
            if(model[2] == ''
               and model[3] == model[4] == model[5] == 0
               and string_has(model[1], RES_KEYS)
               and model[1].isupper()):
                if model[0] != '':
                    code = model[0]
                else:
                    code = None
                item.add_ana_group(model[1], code=code)
                state = GROUP
                group = len(item.ana_items)-1

                index = index + 1
                continue

            # If resource item, add blank group
            elif model[0] != '' and model[1] != '' and model[2] != '' and model[4] != 0:
                # Setup generic resource group for item
                item.add_ana_group('RESOURCE')
                state = GROUP
                group = len(item.ana_items)-1

                # Re-evaluate item under group
                index = index
                continue

            # If total item, add total
            elif(model[2] == ''and model[3] == 0
                 and model[4] == 0 and model[5] != 0
                 and string_has(model[1], SUM_KEYS)
                 and model[5] >= models[index-1][5]):
                item.add_ana_sum(model[1])

                index = index + 1
                continue

            # If weight item, add weight
            elif(model[2] == ''and model[3] == 0
                 and model[4] == 0 and model[5] != 0
                 and string_has(model[1], WEIGHT_KEYS)
                 and model[5] < models[index-1][5]):
                item.add_ana_weight(model[1], Currency(model[5]/models[index-1][5], 3))

                index = index + 1
                continue

            # If times item, add times
            elif(model[2] == '' and model[3] == 0
                 and model[4] == 0 and model[5] != 0
                 and string_has(model[1], TIMES_KEYS)
                 and model[5] < models[index-1][5]):
                item.add_ana_times(model[1], Currency(model[5]/models[index-1][5], 6))

                index = index + 1
                continue

            # If round item, add round
            elif(model[0] == '' and model[2] == '' and model[3] == 0
                 and model[4] == 0 and model[5] != 0
                 and string_has(model[1], ROUND_KEYS)
                 and abs(model[5] - models[index-1][5]) < 1):

                # Check if settigns override enabled
                if round_val == -1:
                    decimal1 = model[5]-int(model[5])
                    decimal2 = model[5]*10 - int(model[5]*10)
                    if decimal2 > 0:
                        pos = 2
                    elif decimal1 > 0:
                        pos = 1
                    else:
                        pos = 0
                    item.add_ana_round(model[1], pos)
                else:
                    item.add_ana_round(model[1], round_val)

                index = index + 1
                break

        # Handle resource group
        elif state == GROUP:
            # If resource item
            if model[0] != '' and model[1] != '' and model[2] != ''  and model[4] != 0:
                # Setup resource item
                code = model[0]
                qty = model[3]
                remarks = None
                # Search if there is a remarks item to be added
                if comment_loc == DOWN:
                    for rem_index in range(1,15):
                        if index+1 < len(models):  # Hack to prevent failures in bad files
                            nxt = models[index+1]
                            if(nxt[0] == nxt[2] == '' and nxt[3] == nxt[4] == nxt[5] == 0 
                               and nxt[1] != '' and (not nxt[1].isupper() or not string_has(nxt[1], RES_KEYS))):
                                if remarks:
                                    remarks = remarks + '\n' + nxt[1]
                                else:
                                    remarks = nxt[1]
                                index = index + 1
                            else:
                                break
                        else:
                            break
                elif comment_loc == UP:
                    for rem_index in range(1,15):
                        if index-rem_index > 0:  # Hack to prevent failures in bad files
                            prv = models[index-rem_index]
                            if(prv[0] == prv[2] == '' and prv[3] == prv[4] == prv[5] == 0
                               and prv[1] != '' and (not prv[1].isupper() or not string_has(prv[1], RES_KEYS))
                               and index-rem_index > item_start):
                                if remarks:
                                    remarks = prv[1] + '\n' + remarks
                                else:
                                    remarks = prv[1]
                            else:
                                break
                        else:
                            break
                    
                # Set resource model
                res = ResourceItemModel(code = code,
                                        description = model[1], 
                                        unit = model[2],
                                        rate = model[4],
                                        vat = 0,
                                        discount = 0)
                item.resources[code] = res
                
                res_items = [code, qty, remarks]
                item.ana_items[group]['resource_list'].append(res_items)

                index = index + 1
                continue

            # Sum of group item
            elif string_has(model[1], RES_KEYS) and 'total' in model[1].lower():
                group = None
                state = ITEM

                index = index + 1
                continue
            
            # If remark item, skip
            elif (model[0] == model[2] == '' and model[3] == model[4] == model[5] == 0
                  and model[1] != '' 
                  and (not model[1].isupper() or not string_has(model[1], RES_KEYS))):
                index = index + 1
                continue
            
            # If blank line, skip
            elif (model[0] == model[1] == model[2] == ''
                  and model[3] == model[4] == model[5] == 0):
                index = index + 1
                continue
            
            # Any other item
            else:
                group = None
                state = ITEM

                continue

        index = index + 1
    return index
        
        
# Data definition classes

class ScheduleItemModel:
    """Class defines a single schedule item along with analysis of rates"""

    # Constants
    (ANA_GROUP, ANA_SUM, ANA_WEIGHT, ANA_TIMES, ANA_ROUND) = (0,1,2,3,4)

    def __init__(self, code, description, unit = None, rate = None,
                 qty = None, category = None,
                 parent = None, remarks = None, ana_remarks = None,
                 colour = None):
        # Database fields
        self.code = code
        self.description = description
        self.unit = unit
        self.rate = rate
        self.qty = qty
        self.remarks = remarks
        self.ana_remarks = ana_remarks
        self.category = category
        self.parent = parent
        self.colour = colour
        # Additional fields
        self.ana_items = []
        self.resources = dict()
        self.results = []

    def add_ana_res(self, item, group, pos = None):
        """Add a resource under resource group"""
        if self.ana_items[group]['itemtype'] == self.ANA_GROUP:
            if pos is not None:
                self.ana_items[group]['resource_list'].insert(pos, item)
            else:
                self.ana_items[group]['resource_list'].append(item)

    def add_ana_group(self, description, resource_list=None, code = None, pos = None):
        """Add a resource group under analysis of rates"""
        resource_list = list() if resource_list is None else resource_list
        item = {'itemtype' : self.ANA_GROUP, 'description' : description, 'code' : code,
                'resource_list' : resource_list}
        if pos is not None:
            self.ana_items.insert(pos, item)
        else:
            self.ana_items.append(item)

    def add_ana_sum(self, description = None, pos = None):
        """Add a summming field under analysis of rates"""
        item = {'itemtype' : self.ANA_SUM, 'description' : description}
        if pos is not None:
            self.ana_items.insert(pos, item)
        else:
            self.ana_items.append(item)

    def add_ana_weight(self, description, weight, pos = None):
        """Add an field weighted cumulative sum under analysis of rates"""
        item = {'itemtype' : self.ANA_WEIGHT, 'description' : description, 'value' : weight}
        if pos is not None:
            self.ana_items.insert(pos, item)
        else:
            self.ana_items.append(item)

    def add_ana_times(self, description, weight, pos = None):
        """Modify the cumulative sum by a factor under analysis of rates"""
        item = {'itemtype' : self.ANA_TIMES, 'description' : description, 'value' : weight}
        if pos is not None:
            self.ana_items.insert(pos, item)
        else:
            self.ana_items.append(item)

    def add_ana_round(self, description, digits, pos = None):
        """Add a rounding field under analysis of rates"""
        item = {'itemtype' : self.ANA_ROUND, 'description' : description, 'value' : digits}
        if pos is not None:
            self.ana_items.insert(pos, item)
        else:
            self.ana_items.append(item)
    
    def get_item(self, path, deep=True):
        if path[0] >= 0 and path[0] < len(self.ana_items):
            item = copy.deepcopy(self.ana_items[path[0]])
            if len(path) == 1:
                if not deep:
                    item['resource_list'] = []
                return ['ana_item', item]
            elif len(path) == 2 and item['itemtype'] == self.ANA_GROUP:
                if path[1] >= 0 and path[1] < len(item['resource_list']):
                    resource_item = copy.copy(item['resource_list'][path[1]])
                    resource = self.resources[resource_item[0]]
                return ['resource_item', resource_item, resource]
                    
    def insert_item(self, item, path):
        if type(item) == dict:
            if item['itemtype'] == self.ANA_GROUP:
                    description = item['description']
                    resource_list = item['resource_list']
                    code = item['code']
                    pos = path[0]
                    self.add_ana_group(description, resource_list, code, pos)
            elif item['itemtype'] == self.ANA_SUM:
                description = item['description']
                pos = path[0]
                self.add_ana_sum(description, pos)
            elif item['itemtype'] == self.ANA_WEIGHT:
                description = item['description']
                weight = item['value']
                pos = path[0]
                self.add_ana_weight(description, weight, pos)
            elif item['itemtype'] == self.ANA_TIMES:
                description = item['description']
                weight = item['value']
                pos = path[0]
                self.add_ana_times(description, weight, pos)
            elif item['itemtype'] == self.ANA_ROUND:
                description = item['description']
                weight = item['value']
                pos = path[0]
                self.add_ana_round(description, weight, pos)
        elif type(item) == list:
            if None in path:
                if self.ana_items[-1]['itemtype'] == self.ANA_GROUP:
                    path = [len(self.ana_items)-1]
                else:
                    return
                    
            if path[0] >= 0 and path[0] < len(self.ana_items):
                if len(path) == 1:
                    self.add_ana_res(item, path[0])
                elif len(path) == 2:
                    self.add_ana_res(item, path[0], path[1])
                return item[0]

    def delete_item(self, path):
        if path is not None:
            if len(path) == 1:
                del self.ana_items[path[0]]
            elif len(path) == 2:
                del self.ana_items[path[0]]['resource_list'][path[1]]

    def evaluate_results(self):
        """Calculate the various amounts under analysis of rates"""
        sum_total = 0
        sum_item = 0
        self.results = []
        for item in self.ana_items:
            if item['itemtype'] == self.ANA_GROUP:
                sum_item = 0
                result = []
                for resource in item['resource_list']:
                    res = self.resources[resource[0]]
                    discount = res.discount if res.discount else 0
                    vat = res.vat if res.vat else 0
                    rate = Currency(res.rate * (100 + vat) * (100 - discount) / 10000)
                    qty = resource[1]
                    total = Currency(Decimal(qty) * Decimal(rate))
                    sum_item = sum_item + total
                    result.append([rate, total])
                sum_total = Currency(sum_total + sum_item)
                result.append(sum_item)
                self.results.append(result)
            elif item['itemtype'] == self.ANA_SUM:
                sum_item = Currency(sum_total)
                self.results.append(sum_total)
            elif item['itemtype'] == self.ANA_WEIGHT:
                result = Currency(sum_item * Decimal(item['value']))
                sum_total = sum_total + result
                self.results.append(result)
            elif item['itemtype'] == self.ANA_TIMES:
                result = Currency(sum_item * Decimal(item['value']))
                sum_total = result
                sum_item = sum_total
                self.results.append(result)
            elif item['itemtype'] == self.ANA_ROUND:
                sum_total = Currency(sum_total, item['value'])
                self.results.append(sum_total)
    
    def get_ana_rate(self):
        # If analysed
        if self.results:
            # If ana group is last item
            if type(self.results[-1]) is list:
                return self.results[-1][-1]
            else:
                return self.results[-1]

    def update_rate(self):
        """Change rate under schedule to one calculated by analysis of rates"""
        if self.results:
            self.rate = self.get_ana_rate()

    def print_analysis(self):
        """Print out analysis of rates to stdout"""
        print(self.code)
        print(self.description)
        if self.ana_remarks is not None:
            print(self.ana_remarks)
        # If resource details fed do full analysis
        if self.resources:
            for itemno, item in enumerate(self.ana_items):
                if item['itemtype'] == self.ANA_GROUP:
                    print(item['code'], item['description'])
                    for resno, resource in enumerate(item['resource_list']):
                        res = self.resources[resource[0]]
                        qty = resource[1]
                        rate = self.results[itemno][resno][0]
                        total = self.results[itemno][resno][1]
                        print([resource[0], res.description, res.unit,
                                 rate, qty, total])
                        if resource[2]:
                            print(resource[2])
                        if res.reference:
                            print(res.reference)
                    result = self.results[itemno][-1]
                    print('TOTAL of ' + str(item['code']), result)
                if item['itemtype'] == self.ANA_SUM:
                    result = self.results[itemno]
                    print(['SUM ', item['description'], result])
                if item['itemtype'] == self.ANA_WEIGHT:
                    result = self.results[itemno]
                    print([item['description'], item['value'], result])
                if item['itemtype'] == self.ANA_TIMES:
                    result= self.results[itemno]
                    print([item['description'], item['value'], result])
                if item['itemtype'] == self.ANA_ROUND:
                    result = self.results[itemno]
                    print([item['description'], item['value'], result])
        # If only skeleton available print without calculation
        else:
            for item in self.ana_items:
                if item['itemtype'] == self.ANA_GROUP:
                    print(item['code'], item['description'])
                    for resource in item['resource_list']:
                        print(resource)
                    print('TOTAL of ' + item['code'])
                if item['itemtype'] == self.ANA_SUM:
                    print(['SUM ', item['description']])
                if item['itemtype'] == self.ANA_WEIGHT:
                    print([item['description'], item['value']])
                if item['itemtype'] == self.ANA_TIMES:
                    print([item['description'], item['value']])
                if item['itemtype'] == self.ANA_ROUND:
                    print([item['description'], item['value']])


class ResourceItemModel:
    """Class defines a single resource item along with analysis of rates"""
    def __init__(self, code, description, unit, rate, vat = None,
                 discount = None, reference = None, category = None):
        # Database fields
        self.code = code
        self.description = description
        self.unit = unit
        self.rate = rate
        self.vat = vat
        self.discount = discount
        self.reference = reference
        self.category = category


# Sqlite database models

database = peewee.SqliteDatabase(None)
database_filename = None

class BaseModelSch(peewee.Model):
    """Base class for all schedule database class definitions"""
    class Meta:
        database = database
        
class ProjectTable(BaseModelSch):
    key = peewee.CharField(primary_key = True)
    value = peewee.CharField()
    
class ScheduleCategoryTable(BaseModelSch):
    description = peewee.CharField(unique = True)
    order = peewee.IntegerField()
    
class ResourceCategoryTable(BaseModelSch):
    description = peewee.CharField(unique = True)
    order = peewee.IntegerField()

class ScheduleTable(BaseModelSch):
    code = peewee.CharField(unique = True)
    description = peewee.CharField()
    unit = peewee.CharField(null = True)
    rate = peewee.DecimalField(decimal_places = 2, auto_round = True, null = True)
    qty = peewee.DecimalField(null = True)
    remarks = peewee.CharField(null = True)
    ana_remarks = peewee.CharField(null = True)
    category = peewee.ForeignKeyField(ScheduleCategoryTable, null = True, on_delete = 'CASCADE', related_name='scheduleitems')
    parent = peewee.ForeignKeyField('self', on_delete = 'CASCADE', null=True, related_name='children')
    order = peewee.IntegerField()
    suborder = peewee.IntegerField(null = True)
    colour = peewee.CharField(null = True)

class ResourceTable(BaseModelSch):
    code = peewee.CharField(unique = True)
    description = peewee.CharField()
    unit = peewee.CharField()
    rate = peewee.DecimalField(decimal_places = 2, auto_round = True)
    vat = peewee.DecimalField(decimal_places = 2, auto_round = True, null = True)
    discount = peewee.DecimalField(decimal_places = 2, auto_round = True, null = True)
    reference = peewee.CharField(null = True)
    category = peewee.ForeignKeyField(ResourceCategoryTable, null = True, on_delete = 'CASCADE', related_name='resources')
    order = peewee.IntegerField()

class SequenceTable(BaseModelSch):
    id_seq = peewee.IntegerField()
    id_sch = peewee.ForeignKeyField(ScheduleTable, on_delete = 'CASCADE', related_name='sequences')
    itemtype = peewee.IntegerField()
    value = peewee.DecimalField(null = True)
    code = peewee.CharField(null = True)
    description = peewee.CharField(null = True)
    class Meta:
        # Add uniqueness constraint
        indexes = ((('id_seq', 'id_sch'),True),)

class ResourceItemTable(BaseModelSch):
    id_sch = peewee.ForeignKeyField(ScheduleTable, on_delete = 'CASCADE', related_name='resourceitems')
    id_seq = peewee.ForeignKeyField(SequenceTable, on_delete = 'CASCADE', related_name='resourceitems')
    id_res = peewee.ForeignKeyField(ResourceTable, on_delete = 'CASCADE', related_name='resourceitems')
    qty = peewee.DecimalField()
    remarks = peewee.CharField(null = True)


# Data base handler

class ScheduleDatabase:

    def __init__(self):
        self.database = database
        self.libraries = OrderedDict()
        
    ## Database management
    
    def create_new_database(self, filename=None):
        global database_filename
        
        if filename:
            self.open_database(filename)
            database_filename = filename
        else:
            self.open_database(':memory:')
            database_filename = None
        # Create tables
        tables = [ProjectTable, ScheduleTable, ResourceTable, 
                  ScheduleCategoryTable, ResourceCategoryTable,
                  SequenceTable, ResourceItemTable]
        self.database.create_tables(tables)
        
        # Update default project settings
        self.set_project_settings(misc.default_project_settings)
        log.info('ScheduleDatabase - create_new_database - database tables created')

    def open_database(self, filename):
        global database_filename
        
        # Database intitialisation
        self.database.init(filename)
        # Set current database filename
        database_filename = filename
        # Enable foreign key support for sqlite database
        self.database.execute_sql('PRAGMA foreign_keys=ON;')
        
        return True
        
    def validate_database(self, filename):
        # Try to open database and check database compatibility
        try:
            connection = sqlite3.connect(filename)
            cursor = connection.cursor()
            cursor.execute('''SELECT value FROM ProjectTable where key="file_version"''')
            proj_version = cursor.fetchone()
            
            if proj_version[0] > misc.PROJECT_FILE_VER:
                return [False, "Newer project file version found. Please use the latest application version."]
            elif proj_version[0] == 'GESTIMATOR_FILE_REFERENCE_VER_1':
                self.migrate_from_ver_1(filename)
                
            cursor.execute('''UPDATE ProjectTable SET value = ? WHERE key = "file_version"''', (misc.PROJECT_FILE_VER,))
            connection.commit()
            connection.close()
        except:
            return [False, 'Error validating file. unknown/corrupt file.']
        
        return [True]
        
    def migrate_from_ver_1(self, filename):
        log.info('ScheduleDatabase - migrate_from_ver_1 called - ' + filename)
        
        # Open database
        my_db = peewee.SqliteDatabase(filename)
        migrator = SqliteMigrator(my_db)
        
        colour = peewee.CharField(null = True)
        
        with my_db.transaction():
            migrate(migrator.add_column('ScheduleTable', 'colour', colour))
            
        log.info('ScheduleDatabase - database migrated - ' + filename)
        
    def close_database(self):
        global database_filename
        
        self.database.close()
        database_filename = None
        
    def get_database_name(self):
        return database_filename
        
    def add_library(self, filename):
        """Add a new library to database model"""
        try:
            # Migrate database to latest format
            ret_code = self.validate_database(filename)
            if ret_code[0] == True:
                # Add library
                library = peewee.SqliteDatabase(filename)
                with peewee.Using(library, [ProjectTable]):
                    name = self.get_project_settings()['project_name']
                log.info('ScheduleDatabase - add_library - library added - ' + name)
            else:
                log.error('ScheduleDatabase - add_library - Error validating file')
                return False
        except:
            log.error('ScheduleDatabase - add_library - Error opening file')
            return False
        self.libraries[name] = library
        return True
        
    def using_library(self, name):
        """Return context manager for using database name"""
        if name in self.libraries:
            tables = [ProjectTable, ScheduleTable, ResourceTable, 
                  ScheduleCategoryTable, ResourceCategoryTable,
                  SequenceTable, ResourceItemTable]
            return peewee.Using(self.libraries[name], tables)
        else:
            return None
            
    def get_library_names(self):
        return list(self.libraries.keys())
      
        
    ## Project settings
        
    @database.atomic()
    def get_project_settings(self):
        items = ProjectTable.select()
        settings = dict()
        for item in items:
            settings[item.key] = item.value
        return settings
        
    @database.atomic()
    def set_project_settings(self, settings):
        # Clear settings
        ProjectTable.delete().execute()
        # Add settings
        for key, value in settings.items():
            ProjectTable.create(key=key, value=value)
    
            
    ## Resource category methods
    
    @database.atomic()
    def get_resource_categories(self):
        categories = ResourceCategoryTable.select().order_by(ResourceCategoryTable.order)
        cat_list = []
        for category in categories:
            cat_list.append(category.description)
        return cat_list
        
    @undoable
    @database.atomic()
    def update_resource_category(self, category, value):
        """Updates schedule item data"""
        try:
            ResourceCategoryTable.update(description = value).where(ResourceCategoryTable.description == category).execute()
        except:
            return False
            
        yield "Update resource category '{}' to '{}'".format(category, value), True
        ResourceCategoryTable.update(description = category).where(ResourceCategoryTable.description == value).execute()
        
    @database.atomic()
    def insert_resource_category_atomic(self, category, path=None):
        """If path is None add as first item; If path[0] = -1, add as last item""" 
        
        if path:
            # Path specified add at path
            cat_len = ResourceCategoryTable.select().count()
            if path[0] >= cat_len or path[0] == -1:
                order = cat_len
            else:
                order = path[0]+1
        else:
            # No path specified, add at start
            order = 0
            
        ResourceCategoryTable.update(order = ResourceCategoryTable.order + 1).where(ResourceCategoryTable.order >= order).execute()
            
        new_cat = ResourceCategoryTable(description=category, order=order)
        try:
            new_cat.save()
        except:
            log.error('ScheduleDatabase - insert_resource_category - saving record failed for ' + category)
            return False
            
        return order
            
    @undoable
    @database.atomic()
    def insert_resource_category(self, category, path=None):
        ret = self.insert_resource_category_atomic(category, path)
        
        yield "Add resource category item at path:'{}'".format(str(path)), ret
        # Delete added resources
        self.delete_resource_category(category)
        
    @database.atomic()
    def delete_resource_category_atomic(self, category_name):
        """Delete resource category"""
        try:
            old_item = ResourceCategoryTable.select().where(ResourceCategoryTable.description == category_name).get()
            old_order = old_item.order
            old_item.delete_instance()
            # Update order values
            ResourceCategoryTable.update(order = ResourceCategoryTable.order - 1).where(ResourceCategoryTable.order > old_order).execute()
        except ResourceCategoryTable.DoesNotExist:
            return False
            
        return old_order
            
    @undoable
    @database.atomic()
    def delete_resource_category(self, category_name):
        
        old_order = self.delete_resource_category_atomic(category_name)
        
        yield "Delete resource category:'{}'".format(str(category_name))
        # Add back deleted resources
        self.insert_resource_category(category_name, [old_order])


    ## Resource methods
    
    @database.atomic()
    def get_resource(self, code, modify_code=False):
        try:
            item = ResourceTable.select().where(ResourceTable.code == code).get()
        except ResourceTable.DoesNotExist:
            return None
        
        if modify_code and len(item.code.split(':')) == 1:
            proj_code = self.get_project_settings()['project_resource_code']
            code = proj_code + ':' + item.code
        else:
            code = item.code

        return ResourceItemModel(code = code,
                                 description = item.description,
                                 unit = item.unit,
                                 rate = item.rate,
                                 vat = item.vat,
                                 discount = item.discount,
                                 reference = item.reference,
                                 category = item.category.description)

    @database.atomic()
    def get_resource_table(self, category = None, flat=False, modify_code=False):
        res = OrderedDict()
        proj_code = self.get_project_settings()['project_resource_code']
        
        if not flat:
            if category is not None:
                try:
                    categories = [ResourceCategoryTable.select().where(ResourceCategoryTable.description == category).get()]
                except ResourceCategoryTable.DoesNotExist:
                    log.error('ScheduleDatabase - get_resource_table - Category not found - ' + category)
                    return res
            else:
                categories = ResourceCategoryTable.select().order_by(ResourceCategoryTable.order)

            for category in categories:
                res_cat = ResourceTable.select().where(ResourceTable.category == category.id).order_by(ResourceTable.order)
                items = OrderedDict()
                category_name = category.description
                if category_name is None or category_name == '':
                    category_name = 'UNCATEGORISED'
                for item in res_cat:
                    if modify_code and len(item.code.split(':')) == 1:
                        code = proj_code + ':' + item.code
                    else:
                        code = item.code
                    description = item.description
                    unit = item.unit
                    rate = item.rate
                    vat = item.vat
                    discount = item.discount
                    reference = item.reference
                    items[code] = [code, description, unit, 
                                   rate, vat, discount, reference]
                res[category_name] = items
        else:
            if category:
                try:
                    category_model = ResourceCategoryTable.select().where(ResourceCategoryTable.description == category).get()
                except ResourceCategoryTable.DoesNotExist:
                    log.error('ScheduleDatabase - get_resource_table - Category not found - ' + category)
                    return res
                res_cat = ResourceTable.select().where(ResourceTable.category == category_model.id).order_by(ResourceTable.order)
            else:
                res_cat = ResourceTable.select().order_by(ResourceTable.order)
            for item in res_cat:
                if modify_code and len(item.code.split(':')) == 1:
                    code = proj_code + ':' + item.code
                else:
                    code = item.code
                description = item.description
                unit = item.unit
                rate = item.rate
                vat = item.vat
                discount = item.discount
                reference = item.reference
                category = item.category.description
                res[code] = [code, description, unit, 
                             rate, vat, discount, reference, category]
                
        return res
    
    @database.atomic()
    def get_resource_dependency(self, itemdict):
        """Get schedule items depending on resource category"""
        
        items = set()
        
        for path, code in itemdict.items():
            if len(path) == 1:
                try:
                    category = ResourceCategoryTable.select().where(ResourceCategoryTable.description == code).get()
                    for res in category.resources:
                        if res.resourceitems:
                            items.add(res.code)
                except ResourceCategoryTable.DoesNotExist:
                    continue
            elif len(path) == 2:
                try:
                    res = ResourceTable.select().where(ResourceTable.code == code).get()
                    if res.resourceitems:
                        items.add(res.code)
                except ResourceTable.DoesNotExist:
                    continue
        return items
            
    def resource_has_dependency(self, code):
        """Check if the resource has dependency"""
        try:
            item = ResourceTable.select().where(ResourceTable.code == code).get()
            if item.resourceitems:
                return True
            else:
                return False
        except ResourceTable.DoesNotExist:
            return False
            
    @database.atomic()
    def delete_resource_item_atomic(self, code):
        """Delete schedule item"""
        try:
            old_item = ResourceTable.select().where(ResourceTable.code == code).get()
            old_order = old_item.order
            old_category_order = old_item.category.order
            
            if old_order > 0:
                old_res_path = [old_category_order, old_order-1]
            else:
                old_res_path = [old_category_order]
            
            old_item.delete_instance()
            # Update order values
            ResourceTable.update(order = ResourceTable.order - 1).where((ResourceTable.category == old_item.category.id) & (ResourceTable.order > old_order)).execute()
        except ResourceTable.DoesNotExist:
            return False
            
        return old_res_path
        
    @undoable
    @database.atomic()
    def delete_resource_item(self, code):
        old_res_model = self.get_resource(code)
        old_res_path = self.delete_resource_item_atomic(code)
        
        yield "Delete resource item:'{}'".format(str(code)), old_res_path
        # Add back deleted resources
        self.insert_resource(old_res_model, old_res_path)
        
    @database.atomic()
    def delete_resource_atomic(self, selected):
        """Delete resource elements"""
        
        unique_codes = set()
        unique_cats = set()
        for path, code in selected.items():
            if len(path) == 1:
                ress = self.get_resource_table(category=code, flat=True)
                for res_code in ress:
                    unique_codes.add(res_code)
                unique_cats.add(code)
            # Resource Items
            if len(path) == 2:
                unique_codes.add(code)
        
        # Handle sub items first     
        for code in unique_codes:
            self.delete_resource_item_atomic(code)
                
        # Handle categories second
        for code in unique_cats: 
            self.delete_resource_category_atomic(code)
                
    @database.atomic()
    def delete_resource(self, selected):
        """Undoable Delete resource elements"""
        with group("Delete resource items"):
            
            unique_codes = set()
            unique_cats = set()
            for path, code in selected.items():
                if len(path) == 1:
                    ress = self.get_resource_table(category=code, flat=True)
                    for res_code in ress:
                        unique_codes.add(res_code)
                    unique_cats.add(code)
                # Resource Items
                if len(path) == 2:
                    unique_codes.add(code)
            
            # Handle sub items first     
            for code in unique_codes:
                self.delete_resource_item(code)
                    
            # Handle categories second
            for code in unique_cats: 
                self.delete_resource_category(code)

    @database.atomic()
    def insert_resource_atomic(self, resource, path=None):
        
        res_category_added = None
        
        # If path is specified
        if path:
            # Get category by order
            try:
                category = ResourceCategoryTable.select().where(ResourceCategoryTable.order == path[0]).get()
            except ResourceCategoryTable.DoesNotExist:
                log.error('ScheduleDatabase - insert_resource - category could not be found for ' + str(path))
                return False
            category_id = category.id
            if len(path) == 1:
                # Add as first item of category
                order = 0
                ResourceTable.update(order = ResourceTable.order + 1).where(ResourceTable.category == category_id).execute()
            if len(path) == 2:
                # Add after selected item
                order = path[1] + 1
                ResourceTable.update(order = ResourceTable.order + 1).where((ResourceTable.order >= order) & (ResourceTable.category == category_id)).execute()
        
        # If path not specified
        else:
            # Get category from database
            if resource.category is None or resource.category == '':
                category_name = 'UNCATEGORISED'
            else:
                category_name = resource.category
            try:
                category = ResourceCategoryTable.select().where(ResourceCategoryTable.description == category_name).get()
                category_id = category.id
                # Append at end of category
                order = ResourceTable.select().where(ResourceTable.category == category_id).count()
            except ResourceCategoryTable.DoesNotExist:
                # Add new category at end and add item under it
                if self.insert_resource_category_atomic(category_name, path=[-1]) is not None:
                    category = ResourceCategoryTable.select().where(ResourceCategoryTable.description == category_name).get()
                    category_id = category.id
                    res_category_added = category_name
                    order = 0
                else:
                    log.error('ScheduleDatabase - insert_resource - category could not be set - ' + str(category_name))
                    return False
        
        res = ResourceTable(code = resource.code,
                            description = resource.description,
                            unit = resource.unit,
                            rate = resource.rate,
                            vat = resource.vat,
                            discount = resource.discount,
                            reference = resource.reference,
                            category = category_id,
                            order = order)
                            
        path_added = [category.order, order]
        
        try:
            res.save()
        except peewee.IntegrityError:
            log.warning('ScheduleDatabase - insert_resource - Item code exists, Item not added - ' + resource.code)
            return False
            
        return [path_added, res_category_added]
        
    @undoable
    @database.atomic()
    def insert_resource(self, resource, path=None):

        ret = self.insert_resource_atomic(resource, path)
        if ret:
            [path_added, res_category_added] = ret
        else:
            path_added = None
            res_category_added = None
    
        yield "Add resource data item at path:'{}'".format(str(path)), [path_added, res_category_added]
        # Delete added resources
        if path_added:
            self.delete_resource_item_atomic(resource.code)
        # Delete any category added
        if res_category_added:
            self.delete_resource_category_atomic(res_category_added)
                
    @database.atomic()
    def insert_resource_multiple_atomic(self, resources, path=None, preserve_structure=False):
    
        inserted = OrderedDict()
        for resource in resources:

            [path_added, res_category_added] = self.insert_resource_atomic(resource, path)
            
            # Modify inserted
            if res_category_added:
                inserted[(path_added[0],)] = res_category_added
                
            inserted[tuple(path_added)] = resource.code
            
            if not preserve_structure:
                # Update path
                path = path_added
        
        return inserted
        
    @undoable
    @database.atomic()
    def insert_resource_multiple(self, resources, path=None, preserve_structure=False):
        
        inserted = self.insert_resource_multiple_atomic(resources, path, preserve_structure)

        yield "Add resource items at path:'{}'".format(path), inserted
        
        # Delete added item
        self.delete_resource_atomic(inserted)
            
    @undoable
    @database.atomic()
    def update_resource(self, code, newvalue=None, column=None, res_model=None):
        
        # Obtain resource item
        try:
            res = ResourceTable.select().where(ResourceTable.code == code).get()
        except ResourceTable.DoesNotExist:
            return False
        
        # Individual column update
        if column is not None:
            if column == 0:
                oldvalue = res.code
                res.code = newvalue
            elif column == 1:
                oldvalue = res.description
                res.description = newvalue
            elif column == 2:
                oldvalue = res.unit
                res.unit = newvalue
            elif column == 3:
                oldvalue = res.rate
                res.rate = newvalue
            elif column == 4:
                oldvalue = res.vat
                res.vat = newvalue
            elif column == 5:
                oldvalue = res.discount
                res.discount = newvalue
            elif column == 6:
                oldvalue = res.reference
                res.reference = newvalue
        
        # Resource model update
        elif res_model:
            try:
                category = ResourceCategoryTable.select().where(ResourceCategoryTable.description == res_model.category).get()
                category_id = category.id
                order = res.order
            except:
                # Add new category at end and add resource under it
                if self.insert_resource_category_atomic(res_model.category, path=[-1]) is not None:
                    category = ResourceCategoryTable.select().where(ResourceCategoryTable.description == res_model.category).get()
                    category_id = category.id
                    order = 0
                else:
                    log.error('ScheduleDatabase - update_resource - category could not be set - ' + str(category_name))
                    return False
            
            # Undo values
            old_model = copy.copy(res_model)
            category_id_old = res.category
            
            res.code = res_model.code
            res.description = res_model.description
            res.unit = res_model.unit
            res.rate = res_model.rate
            res.vat = res_model.vat
            res.discount = res_model.discount
            res.reference = res_model.reference
            res.category = category_id
            res.order = order
            
        # Save resource
        try:
            res.save()
        except:
            log.error('ScheduleDatabase - update_resource - Error saving resource')
            return False
            
        yield "Update resource '{}'".format(str(code)), True
        
        # Individual column update
        if column is not None:
            if column != 0:
                res = ResourceTable.select().where(ResourceTable.code == code).get()
            else:
                res = ResourceTable.select().where(ResourceTable.code == newvalue).get()
                
            if column == 0:
                res.code = oldvalue
            elif column == 1:
                res.description = oldvalue
            elif column == 2:
                res.unit = oldvalue
            elif column == 3:
                res.rate = oldvalue
            elif column == 4:
                res.vat = oldvalue
            elif column == 5:
                res.discount = oldvalue
            elif column == 6:
                res.reference = oldvalue
        
        # Resource model update
        elif res_model:
            res.code = old_model.code
            res.description = old_model.description
            res.unit = old_model.unit
            res.rate = old_model.rate
            res.vat = old_model.vat
            res.discount = old_model.discount
            res.reference = old_model.reference
            res.category = category_id_old
            
        # Save resource
        res.save()
        
    def get_new_resource_category_name(self):
        categories =  ResourceCategoryTable.select(ResourceCategoryTable.description).where(ResourceCategoryTable.description.startswith('_CATEGORY'))
        
        cat_list = []
        for category in categories:
            cat_list.append(misc.human_code(category.description))
            
        if categories:
            last_code = sorted(cat_list)[-1]
            if type(last_code[-1]) is int:
                new_code = '_CATEGORY' + str(last_code[-1]+1)
            else:
                new_code = '_CATEGORY1'
        else:
            new_code = '_CATEGORY1'
        return new_code
        
    def get_new_resource_code(self, shift=0, exclude=None, near_item_code=None):
    
        if near_item_code is not None:
            parsed = misc.human_code(near_item_code)
            if type(parsed[-1]) is int:
                new_code_parsed = parsed[:-1] + [parsed[-1]+ (1+shift)]
                new_code = ''
                for part in new_code_parsed:
                    new_code = new_code + str(part)
                if not ResourceTable.select().where(ResourceTable.code == new_code).exists():
                    return new_code
                        
        # Fall back
        ress = ResourceTable.select(ResourceTable.code).where(ResourceTable.code.startswith('MR.'))
        
        # If fall through
        if near_item_code:
            shift = 0
        
        # Add exisitng default items
        code_list = []
        for res in ress:
            split_up = misc.human_code(res.code)
            if len(split_up) == 2 and split_up[0] == 'MR.' and type(split_up[-1]) is int:
                code_list.append(split_up)
        
        # Add items specified by exclude
        if exclude:
            for code in exclude:
                code_list.append(misc.human_code(code))
            
        if code_list:
            last_code = sorted(code_list)[-1]
            if type(last_code[-1]) is int:
                new_code = 'MR.' + str(int(last_code[-1])+1+shift)
            else:
                new_code = 'MR.' + str(1+shift)
        else:
            new_code = 'MR.' + str(1+shift)
        return new_code
        
    @database.atomic()
    def check_insert_resource(self, resource):
        
        # Get order asif new item
        order = ResourceTable.select().count()
        
        # Get category from database
        try:
            category = ResourceCategoryTable.select().where(ResourceCategoryTable.description == resource.category).get()
            category_id = category.id
        except ResourceCategoryTable.DoesNotExist:
            category_id = None
        
        # Setup item
        res = ResourceTable(code = resource.code,
                            description = resource.description,
                            unit = resource.unit,
                            rate = resource.rate,
                            vat = resource.vat,
                            discount = resource.discount,
                            reference = resource.reference,
                            category = category_id,
                            order = order)
                            
        # Try inserting item in database and then rollback changes
        with self.database.transaction() as txn:
            with self.database.savepoint() as sp:
                try:
                    res.save()
                    # If successfully completed, rollback and return True
                    sp.rollback()
                    return True
                except:
                    sp.rollback()
                    return False
        # If error return False
        return False
        
    @undoable
    @database.atomic()
    def update_resource_from_database(self, databasename):
        if databasename in self.get_library_names():
            undodict = dict()
            with self.using_library(databasename):
                res_new = self.get_resource_table(flat=True, modify_code=True)
            ress = ResourceTable.select()
            for res in ress:
                if res.code in res_new:
                    undodict[res.code] = [res.rate, res.vat, res.discount, res.reference]
                    res.rate = res_new[res.code][3]
                    res.vat = res_new[res.code][4]
                    res.discount = res_new[res.code][5]
                    res.reference = res_new[res.code][6]
                    res.save()
        
        yield "Update rates from database:'{}'".format(databasename)
        
        ress = ResourceTable.select()
        for res in ress:
            if res.code in undodict:
                res.rate = undodict[res.code][0]
                res.vat = undodict[res.code][0]
                res.discount = undodict[res.code][0]
                res.remarks = undodict[res.code][0]
                res.save()
        
    ## Schedule category methods
    
    @database.atomic()
    def get_schedule_categories(self):
        categories = ScheduleCategoryTable.select().order_by(ScheduleCategoryTable.order)
        cat_list = []
        for category in categories:
            cat_list.append(category.description)
        return cat_list
        
    @undoable
    @database.atomic()
    def update_schedule_category(self, category, value):
        """Updates schedule item data"""
        try:
            ScheduleCategoryTable.update(description = value).where(ScheduleCategoryTable.description == category).execute()
        except:
            return False
            
        yield "Update schedule category '{}' to '{}'".format(category, value), True
        ScheduleCategoryTable.update(description = category).where(ScheduleCategoryTable.description == value).execute()
            
    @database.atomic()
    def insert_schedule_category_atomic(self, category, path=None):
        """If path is None add as first item; If path[0] = -1, add as last item""" 
        
        if path:
            # Path specified add at path
            cat_len = ScheduleCategoryTable.select().count()

            if path[0] >= cat_len or path[0] == -1:
                order = cat_len
            else:
                order = path[0]+1
        else:
            # No path specified, add at start
            order = 0
            
        # Update order
        ScheduleCategoryTable.update(order = ScheduleCategoryTable.order + 1).where(ScheduleCategoryTable.order >= order).execute()
            
        new_cat = ScheduleCategoryTable(description=category, order=order)
        try:
            new_cat.save()
        except:
            log.error('ScheduleDatabase - insert_schedule_category - saving record failed for ' + category)
            return False
            
        return order
        
    @undoable
    @database.atomic()
    def insert_schedule_category(self, category, path=None):
        order = self.insert_schedule_category_atomic(category, path)
        
        yield "Add schedule category item at path:'{}'".format(str(path)), order
        # Delete added resources
        self.delete_schedule_category_atomic(category)
        
    @database.atomic()
    def delete_schedule_category_atomic(self, category_name):
        """Delete resource category"""
        try:
            old_item = ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == category_name).get()
            old_order = old_item.order
            old_item.delete_instance()
            # Update order values
            ScheduleCategoryTable.update(order = ScheduleCategoryTable.order - 1).where(ScheduleCategoryTable.order > old_order).execute()
        except ScheduleCategoryTable.DoesNotExist:
            return False
        
        return old_order
            
    @undoable
    @database.atomic()
    def delete_schedule_category(self, category_name):
        old_order = self.delete_schedule_category_atomic(category_name)
        
        yield "Delete schedule category:'{}'".format(str(category_name)), old_order
        # Add back deleted resources
        self.insert_schedule_category(category_name, [old_order])
        
    ## Schedule item methods

    @database.atomic()
    def get_item(self, code, modify_res_code=True, copy_ana=True):
        try:
            item = ScheduleTable.select().where(ScheduleTable.code == code).get()
        except ScheduleTable.DoesNotExist:
            return None

        res_models = dict()
        proj_code = self.get_project_settings()['project_resource_code']
        parent = None
        if item.parent:
            try:
                parent_item = ScheduleTable.select().where(ScheduleTable.id == item.parent).get()
                parent = parent_item.code
            except ScheduleTable.DoesNotExist:
                log.warning('ScheduleDatabase - get_item - Parent not found for ' + code)
        sch_model = ScheduleItemModel(code = item.code,
                                      description = item.description,
                                      unit = item.unit,
                                      rate = item.rate,
                                      qty = item.qty,
                                      remarks = item.remarks,
                                      ana_remarks = item.ana_remarks,
                                      category = item.category.description,
                                      parent = parent,
                                      colour = item.colour)
        
        if copy_ana:
            for seq in item.sequences:
                if seq.itemtype == ScheduleItemModel.ANA_GROUP:
                    ress = ResourceItemTable.select().where(ResourceItemTable.id_sch == item.id
                                                            and ResourceItemTable.id_seq == seq.id)
                    res_list = []
                    for res in ress:
                        # If already derived item retain code
                        if modify_res_code == False or len((res.id_res.code).split(':')) > 1 or proj_code == '':
                            mod_code = res.id_res.code
                        # Modify code
                        else:
                            mod_code = proj_code + ':' + res.id_res.code
                        res_list.append([mod_code, res.qty, res.remarks])
                        res_model = self.get_resource(res.id_res.code)
                        res_model.code = mod_code  # Modify resource code
                        res_models[mod_code] = res_model
                    sch_model.add_ana_group(seq.description, res_list, seq.code)
                elif seq.itemtype == ScheduleItemModel.ANA_SUM:
                    sch_model.add_ana_sum(seq.description)
                elif seq.itemtype == ScheduleItemModel.ANA_WEIGHT:
                    sch_model.add_ana_weight(seq.description, seq.value)
                elif seq.itemtype == ScheduleItemModel.ANA_TIMES:
                    sch_model.add_ana_times(seq.description, seq.value)
                elif seq.itemtype == ScheduleItemModel.ANA_ROUND:
                    sch_model.add_ana_round(seq.description, seq.value)
            sch_model.resources = res_models
            sch_model.evaluate_results()
        return sch_model

    @database.atomic()
    def get_item_table(self, category = None, flat=False):
        sch_table = OrderedDict()
        
        if not flat:
            if category is not None:
                try:
                    categories = [ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == category).get()]
                except ScheduleCategoryTable.DoesNotExist:
                    log.error('ScheduleDatabase - get_resource_table - Category not found - ' + category)
                    return
            else:
                categories = ScheduleCategoryTable.select().order_by(ScheduleCategoryTable.order)
                
            for category in categories:
                cat_dict = OrderedDict()
                items = ScheduleTable.select().where((ScheduleTable.category == category.id) & (ScheduleTable.parent == None)).order_by(ScheduleTable.order)
                for item in items:
                    child_list = []
                    parent_list = [item.code, item.description, item.unit, item.rate, item.qty, item.remarks, item.colour]
                    children = ScheduleTable.select().where(ScheduleTable.parent == item.id).order_by(ScheduleTable.suborder)
                    for child in children:
                        child_list.append([child.code, child.description, child.unit,
                                      child.rate, child.qty, child.remarks, child.colour])
                    cat_dict[item.code] = (parent_list, child_list,)
                category_name = category.description
                if category_name is None or category_name == '':
                    category_name = 'UNCATEGORISED'
                sch_table[category_name] = cat_dict
        else:
            if category is not None:
                try:
                    category_model = ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == category).get()
                except ScheduleTable.DoesNotExist:
                    log.error('ScheduleDatabase - get_resource_table - Category not found - ' + category)
                    return
                items = ScheduleTable.select().where(ScheduleTable.category == category_model.id).order_by(ScheduleTable.order, ScheduleTable.suborder)
            else:
                items = ScheduleTable.select().order_by(ScheduleTable.category.order, ScheduleTable.order, ScheduleTable.suborder)
            
            for item in items:
                item_list = [item.code, item.description, item.unit, 
                               item.rate, item.qty, item.remarks, 
                               item.category.description, item.colour]
                sch_table[item.code] = item_list
                
        return sch_table
        
    @undoable
    @database.atomic()
    def update_rates(self, codes = None):
        old_rates = dict()
        if codes is None:
            sch_rows = ScheduleTable.select()
        else:
            sch_rows = ScheduleTable.select().where(ScheduleTable.code << codes)
        for sch_row in sch_rows:
            sch = self.get_item(sch_row.code)
            sch.update_rate()
            
            old_rates[sch_row.code] = sch_row.rate
            
            sch_row.rate = sch.rate
            sch_row.save()
        
        yield "Update schedule item rates", True
        
        if codes is None:
            sch_rows = ScheduleTable.select()
        else:
            sch_rows = ScheduleTable.select().where(ScheduleTable.code << codes)
        for sch_row in sch_rows:
            sch_row.rate = old_rates[sch_row.code]
            sch_row.save()
        
    @undoable
    @database.atomic()
    def update_item_schedule(self, code, value, col):
        """Updates schedule item data"""
        try:
            sch = ScheduleTable.select().where(ScheduleTable.code == code).get()
        except ScheduleTable.DoesNotExist:
            return False

        if col == 0:
            old_value = sch.code
            sch.code = value
        elif col == 1:
            old_value = sch.description
            sch.description = value
        elif col == 2:
            old_value = sch.unit
            sch.unit = value
        elif col == 3:
            old_value = sch.rate
            sch.rate = value
        elif col == 4:
            old_value = sch.qty
            sch.qty = value
        elif col == 6:
            old_value = sch.remarks
            sch.remarks = value
        
        try:
            sch.save()
        except:
            return False
            
        yield "Update schedule item '{}'".format(str(code)), True
        if col != 0:
            sch = ScheduleTable.select().where(ScheduleTable.code == code).get()
        else:
            sch = ScheduleTable.select().where(ScheduleTable.code == value).get()
            
        if col == 0:
            sch.code = old_value
        elif col == 1:
            sch.description = old_value
        elif col == 2:
            sch.unit = old_value
        elif col == 3:
            sch.rate = old_value
        elif col == 4:
            sch.qty = old_value
        elif col == 6:
            sch.remarks = old_value
        
        sch.save()
        
    @undoable
    @database.atomic()
    def update_item_colour(self, codes, colour):
        """Updates schedule item colour"""
        
        old_values = dict()
        
        for code in codes:
            try:
                sch = ScheduleTable.select().where(ScheduleTable.code == code).get()
            except ScheduleTable.DoesNotExist:
                return False

            old_values[code] = sch.colour
            sch.colour = colour
        
            try:
                sch.save()
            except:
                return False
            
        yield "Update schedule item colour '{}'".format(str(code)), True

        for code, old_value in old_values.items():
            sch = ScheduleTable.select().where(ScheduleTable.code == code).get()
            sch.colour = old_value        
            sch.save()
        
    def update_item_atomic(self, sch_model):
        """Updates schedule item i/c analysis"""
        return self.insert_item_atomic(sch_model, path=None, update=True)

    def update_item(self, sch_model):
        """Updates schedule item i/c analysis"""
        return self.insert_item(sch_model, path=None, update=True)
    
    @database.atomic()
    def insert_item_atomic(self, item, path=None, update=False, number_with_path=False):
        
        sch_category_added = None
        code = item.code
        path_added = path
        ress_added = OrderedDict()
        
        # Get category and parent if path not specified or update
        if path is None or update:
        
            # Get category from database
            if item.category is None or item.category == '':
                category_name = 'UNCATEGORISED'
            else:
                category_name = item.category
            try:
                category = ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == category_name).get()
                category_id = category.id
            except ScheduleCategoryTable.DoesNotExist:
                # Add new category at end
                if self.insert_schedule_category_atomic(category_name, path=[-1]) is not None:
                    category = ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == category_name).get()
                    category_id = category.id
                    sch_category_added = category.description
                else:
                    log.error('ScheduleDatabase - insert_item - Category could not be set - ' + str(category_name))
                    return False
                
            # Get parent item from database
            parent_id = None
            if item.parent is not None:
                try:
                    parent = ScheduleTable.select().where(ScheduleTable.code == item.parent).get()
                    parent_id = parent.id
                except ScheduleTable.DoesNotExist:
                    log.warning('ScheduleDatabase - insert_item - Parent not found for ' + str(item.code))
                
        if update:
            # Get old item
            try:
                sch = ScheduleTable.select().where(ScheduleTable.code == item.code).get()
            except ScheduleTable.DoesNotExist:
                return False

            # Update basic values
            sch.code = item.code
            sch.description = item.description
            sch.unit = item.unit
            sch.rate = item.rate
            sch.qty = item.qty
            sch.remarks = item.remarks
            sch.ana_remarks = item.ana_remarks
            sch.category = category_id
            sch.parent = parent_id
            sch.colour = item.colour

            # Delete old analysis items
            for sequence in sch.sequences:
                sequence.delete_instance()
                
        else:
            
            # Setup ScheduleTable
            
            # Insert at last position of category and parent
            if path is None:
                if parent_id:
                    order = parent.order
                    suborder = len(parent.children)
                    # Setup path
                    if suborder == 0:
                        path = [category.order, order]
                    else:   
                        path = [category.order, order, suborder-1]
                else:
                    order = ScheduleTable.select().where((ScheduleTable.category == category_id) & (ScheduleTable.parent == None)).count()
                    suborder = None
                    # Setup path
                    if order == 0:
                        path = [category.order]
                    else:   
                        path = [category.order, order-1]
            
            # Get category by path
            try:
                category = ScheduleCategoryTable.select().where(ScheduleCategoryTable.order == path[0]).get()
            except ScheduleCategoryTable.DoesNotExist:
                log.error('ScheduleDatabase - insert_item - category could not be found for ' + str(path))
                return False
            category_id = category.id
            
            # If category selected, add as first item
            if len(path) == 1:
                order = 0
                suborder = None
                parent_id = None
                # Modify code according to path
                if number_with_path:
                    code = self.get_next_item_code(near_item_code=str(path[0]+1), 
                                                            nextlevel=True)
                ScheduleTable.update(order = ScheduleTable.order + 1).where(ScheduleTable.category == category_id).execute()
            
            # If item selected, add next or under
            elif len(path) == 2:
               
                try:
                    selected_item = ScheduleTable.select().where((ScheduleTable.category == category_id) & (ScheduleTable.order == path[1]) & (ScheduleTable.suborder == None)).get()
                except:
                    log.error('ScheduleDatabase - insert_item - selected item could not be found for ' + str(path))
                    return False
                        
                # Add under
                if selected_item.unit == '' and item.parent is not None:
                    order = path[1]
                    suborder = 0
                    parent_id = selected_item.id
                    # Modify code according to path
                    if number_with_path:
                        code = self.get_next_item_code(near_item_code=selected_item.code, 
                                                                nextlevel=True)
                    ScheduleTable.update(suborder = ScheduleTable.suborder + 1).where((ScheduleTable.category == category_id) & (ScheduleTable.order == order)  & (ScheduleTable.suborder != None)).execute()

                # Add next
                else:
                    order = path[1]+1
                    suborder = None
                    parent_id = None
                    # Modify code according to path
                    if number_with_path:
                        code = self.get_next_item_code(near_item_code=selected_item.code, 
                                                                nextlevel=False)
                    ScheduleTable.update(order = ScheduleTable.order + 1).where((ScheduleTable.category == category_id) & (ScheduleTable.order >= order)).execute()
                        
            # If subitem selected, add next
            elif len(path) == 3:
                
                try:
                    parent_item = ScheduleTable.select().where((ScheduleTable.category == category_id) & (ScheduleTable.order == path[1]) & (ScheduleTable.suborder == None)).get()
                except:
                    log.error('ScheduleDatabase - insert_item - parent item could not be found for ' + str(path))
                    return False
                        
                # Add as next element
                if item.parent is not None:
                    order = path[1]
                    suborder = path[2]+1
                    parent_id = parent_item.id
                    if number_with_path:
                        code = self.get_next_item_code(near_item_code=parent_item.code, 
                                                       nextlevel=True, shift=path[2]+1)
                    ScheduleTable.update(suborder = ScheduleTable.suborder + 1).where((ScheduleTable.suborder >= suborder) & (ScheduleTable.order == order) & (ScheduleTable.category == category_id)).execute()
                # Add as next element of parent
                else:
                    order = path[1]+1
                    suborder = None
                    parent_id = None
                    # Modify code according to path
                    if number_with_path:
                        code = self.get_next_item_code(near_item_code=parent_item.code, 
                                                                nextlevel=False)
                    ScheduleTable.update(order = ScheduleTable.order + 1).where((ScheduleTable.category == category_id) & (ScheduleTable.order >= order)).execute()
            
            # Setup new schedule item
            sch = ScheduleTable(code = code,
                                description = item.description,
                                unit = item.unit,
                                rate = item.rate,
                                qty = item.qty,
                                remarks = item.remarks,
                                ana_remarks = item.ana_remarks,
                                category = category_id,
                                parent = parent_id,
                                order = order,
                                suborder = suborder,
                                colour = item.colour)
                                
            path_added = [sch.category.order, sch.order]
            if sch.suborder is not None:
                path_added.append(sch.suborder)

        try:
            sch.save()
        except peewee.IntegrityError:
            log.warning('ScheduleDatabase - insert_item - Item code exists, Item not added - ' + item.code)
            return False

        # Setup SequenceTable

        for slno, anaitem in enumerate(item.ana_items):
        
            if anaitem['itemtype'] == ScheduleItemModel.ANA_GROUP:
                seq = SequenceTable(id_seq = slno,
                                    id_sch = sch.id,
                                    itemtype = ScheduleItemModel.ANA_GROUP,
                                    value = None,
                                    code = anaitem['code'],
                                    description = anaitem['description'])
                seq.save()
                for resource in anaitem['resource_list']:
                    try:
                        res = ResourceTable.select().where(ResourceTable.code == resource[0]).get()
                    except peewee.DoesNotExist:
                        [res_path, res_cat] = self.insert_resource_atomic(item.resources[resource[0]])
                        res = ResourceTable.select().where(ResourceTable.code == resource[0]).get()
                        
                        ress_added[tuple(res_path)] = res.code
                        if res_cat:
                            ress_added[(res_path[0],)] = res_cat
                        
                    resitem = ResourceItemTable(id_sch = sch.id,
                                                id_seq = seq.id,
                                                id_res = res.id,
                                                qty = resource[1],
                                                remarks = resource[2])
                    resitem.save()
            elif anaitem['itemtype'] == ScheduleItemModel.ANA_SUM:
                seq = SequenceTable(id_seq = slno,
                                    id_sch = sch.id,
                                    itemtype = ScheduleItemModel.ANA_SUM,
                                    value = None,
                                    code = None,
                                    description = anaitem['description'])
                seq.save()
            elif anaitem['itemtype'] == ScheduleItemModel.ANA_WEIGHT:
                seq = SequenceTable(id_seq = slno,
                                    id_sch = sch.id,
                                    itemtype = ScheduleItemModel.ANA_WEIGHT,
                                    value = anaitem['value'],
                                    code = None,
                                    description = anaitem['description'])
                seq.save()
            elif anaitem['itemtype'] == ScheduleItemModel.ANA_TIMES:
                seq = SequenceTable(id_seq = slno,
                                    id_sch = sch.id,
                                    itemtype = ScheduleItemModel.ANA_TIMES,
                                    value = anaitem['value'],
                                    code = None,
                                    description = anaitem['description'])
                seq.save()
            elif anaitem['itemtype'] == ScheduleItemModel.ANA_ROUND:
                seq = SequenceTable(id_seq = slno,
                                    id_sch = sch.id,
                                    itemtype = ScheduleItemModel.ANA_ROUND,
                                    value = anaitem['value'],
                                    code = None,
                                    description = anaitem['description'])
                seq.save()
        
        return [code, path_added, sch_category_added, ress_added]
    
    @undoable
    @database.atomic()
    def insert_item(self, item, path=None, update=False, number_with_path=False):
        
        if update:
            # Get old item model
            old_item = self.get_item(item.code)
            
        # Insert item
        ret = self.insert_item_atomic(item, path=path, update=update, number_with_path=number_with_path)
        
        if ret:
            [code, path_added, sch_category_added, ress_added] = ret
        else:
            return False
        
        if update:    
            message = "Update schedule data item:'{}'".format(item.code)
        else:
            message = "Add schedule data item at path:'{}'".format(str(path_added))
        
        yield message, [code, path_added, sch_category_added, ress_added]
        
        # If update item, insert back old item
        if update:
            self.insert_item_atomic(old_item, update=True)
        else:
            # Delete added resources
            self.delete_item_atomic(item.code)
            # Delete any category added
            if sch_category_added:
                self.delete_schedule_category_atomic(sch_category_added)
                
        # Delete resources
        self.delete_resource_atomic(ress_added)
            
    @database.atomic()
    def insert_item_multiple_atomic(self, items, path=None, number_with_path=False, preserve_structure=False):
        """Function to add multiple schedule items into schedule"""
        
        items_added = OrderedDict()
        net_ress_added = OrderedDict()
        
        for item in items:
            ret = self.insert_item_atomic(item, path=path, number_with_path=number_with_path)
            if ret:
                [code_added, path_added, category_added, ress_added] = ret
                
                if category_added is not None:
                    items_added[(path_added[0],)] = category_added
                    
                items_added[tuple(path_added)] = code_added
                net_ress_added.update(ress_added)
                
                if not preserve_structure:
                    # Update path
                    path = path_added
            else:
                log.error("ScheduleDatabase - insert_item_multiple_atomic - item not added - Code:'{}', Path:'{}'".format(item.code, path))

        return [items_added, net_ress_added]
            
    @undoable
    @database.atomic()
    def insert_item_multiple(self, items, path=None, number_with_path=False, preserve_structure=False):
        """Undoable function to add multiple schedule items into schedule"""

        [items_added, net_ress_added] = self.insert_item_multiple_atomic(items, path, number_with_path, preserve_structure)

        yield "Add schedule items at path:'{}'".format(path), [items_added, net_ress_added]
        
        self.delete_schedule_atomic(items_added)
        self.delete_resource_atomic(net_ress_added)
                
    @database.atomic()
    def delete_item_atomic(self, code):
        """Delete schedule item"""
        try:
            old_item = ScheduleTable.select().where(ScheduleTable.code == code).get()
            old_category_order = old_item.category.order
            old_order = old_item.order
            old_suborder = old_item.suborder
            old_item.delete_instance()
            # Update order values
            if old_item.parent:
                parent_id = old_item.parent.id
                ScheduleTable.update(suborder = ScheduleTable.suborder - 1).where((ScheduleTable.suborder > old_suborder) & (ScheduleTable.parent == parent_id)).execute()
            else:
                ScheduleTable.update(order = ScheduleTable.order - 1).where((ScheduleTable.category == old_item.category.id) & (ScheduleTable.order > old_order)).execute()
        except ScheduleTable.DoesNotExist:
            return False
        
        path_added = [old_category_order, old_order]
        if old_suborder is not None:
            path_added.append(old_suborder)
        
        return path_added
            
    @undoable
    @database.atomic()
    def delete_item(self, code):
    
        old_item_model = self.get_item(code)
        path_added = self.delete_item_atomic(code)
        
        yield "Delete schedule item:'{}'".format(code), path_added
        
        if path_added:
            if len(path_added) == 2:
                if path_added[1] == 0:
                    path = [path_added[0]]
                else:
                    path = [path_added[0], path_added[1]-1]
                    
            elif len(path_added) == 3:
                if path_added[2] == 0:
                    path = [path_added[0], path_added[1]]
                else:
                    path = [path_added[0], path_added[1], path_added[2]-1]
                
            self.insert_item_atomic(old_item_model, path=path, number_with_path=False)
        
    @database.atomic()
    def delete_schedule_atomic(self, selected):
        """Delete schedule elements"""
        
        unique_cats = set()
        unique_parents = set()
        unique_childs = set()
        
        # Populate dicts
        for path, code in reversed(list(selected.items())):
            # Category
            if len(path) == 1:
                try:
                    cat = ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == code).get()
                except:
                    log.error("Category not found :'{}'".format(code))
                    return False
                unique_cats.add(cat.description)
                for parent in cat.scheduleitems:
                    unique_parents.add(parent.code)
                    for child in parent.children:
                        unique_childs.add(child.code)
            # Schedule Items
            elif len(path) == 2:
                # Get main item
                try:
                    parent = ScheduleTable.select().where(ScheduleTable.code == code).get()
                except:
                    log.error("Item not found :'{}'".format(code))
                    return False
                unique_parents.add(code)
                for child in parent.children:
                    unique_childs.add(child.code)
            elif len(path) == 3:
                unique_childs.add(code)
        
        # Handle sub items     
        for code in unique_childs:
            self.delete_item_atomic(code)
            
        # Handle parents     
        for code in unique_parents:
            self.delete_item_atomic(code)
                
        # Handle categories second
        for code in unique_cats: 
            self.delete_schedule_category_atomic(code)
    
    @database.atomic()
    def delete_schedule(self, selected):
        """Delete schedule elements"""
        with group("Delete schedule items"):
            unique_cats = set()
            unique_parents = set()
            unique_childs = set()
            
            # Populate dicts
            for path, code in reversed(list(selected.items())):
                # Category
                if len(path) == 1:
                    try:
                        cat = ScheduleCategoryTable.select().where(ScheduleCategoryTable.description == code).get()
                    except:
                        log.error("Category not found :'{}'".format(code))
                        return False
                    unique_cats.add(cat.description)
                    for parent in cat.scheduleitems:
                        unique_parents.add(parent.code)
                        for child in parent.children:
                            unique_childs.add(child.code)
                # Schedule Items
                elif len(path) == 2:
                    # Get main item
                    try:
                        parent = ScheduleTable.select().where(ScheduleTable.code == code).get()
                    except:
                        log.error("Item not found :'{}'".format(code))
                        return False
                    unique_parents.add(code)
                    for child in parent.children:
                        unique_childs.add(child.code)
                elif len(path) == 3:
                    unique_childs.add(code)
            
            # Handle sub items     
            for code in unique_childs:
                self.delete_item(code)
                
            # Handle parents     
            for code in unique_parents:
                self.delete_item(code)
                    
            # Handle categories second
            for code in unique_cats: 
                self.delete_schedule_category(code)
        
    @database.atomic()
    def get_res_usage(self):
        res_cats = OrderedDict()
        times_values = dict()
        
        # Get sequnces with ANA_TIMES to determine multiplying factor
        times_items = (SequenceTable.select(SequenceTable.id_sch, SequenceTable.value)
                                    .where(SequenceTable.itemtype == ScheduleItemModel.ANA_TIMES))
        for time_item in times_items:
            times_values[time_item.id_sch.id] = time_item.value
                                              
        cats = ResourceCategoryTable.select().order_by(ResourceCategoryTable.order)
        for cat in cats:
            res_list_item = OrderedDict()
            # Get resource items
            res_items = (ResourceItemTable.select(ResourceItemTable, 
                                                      ResourceTable, 
                                                      ResourceCategoryTable)
                                              .join(ResourceTable)
                                              .join(ResourceCategoryTable)
                                              .where(ResourceCategoryTable.id == cat.id)
                                              .order_by(ResourceTable.order))
            for res_item in res_items:
                code = res_item.id_res.code
                res_qty = res_item.qty
                sch_qty = res_item.id_sch.qty if res_item.id_sch.qty else 0
                if res_item.id_sch.id in times_values:
                    mult_factor = times_values[res_item.id_sch.id]
                else:
                    mult_factor = 1
                    
                qty = round(res_qty*sch_qty*mult_factor, 4)
                
                if code in res_list_item:
                    res_list_item[code][3] = res_list_item[code][3] + qty
                else:
                    res_list_item[code] = [code,
                                           res_item.id_res.description,
                                           res_item.id_res.unit,
                                           qty,
                                           res_item.id_res.rate, 
                                           res_item.id_res.vat,
                                           res_item.id_res.discount]
            res_cats[cat.description] = res_list_item
        return res_cats
        
    @undoable
    @database.atomic()
    def assign_auto_item_numbers(self):
        """Assign automatic item numbers to schedule items"""
        # Change all items to prevent uniqueness errors
        ScheduleTable.update(code = ScheduleTable.code.concat('_')).execute()
        
        undodict = dict()
        code_cat_dict = dict()
        
        categories = ScheduleCategoryTable.select().order_by(ScheduleCategoryTable.order)
        for category in categories:
            code_cat_dict[category.id] = category.order + 1
        
        items = ScheduleTable.select().order_by(category.id, ScheduleTable.order, ScheduleTable.suborder)
        for item in items:
            
            code_cat = code_cat_dict[item.category.id]
            code_item = item.order + 1
            
            if item.parent == None:
                # If only one category reduce level of item numbering
                if len(code_cat_dict) == 1:
                    code = str(code_item)
                else:
                    code = str(code_cat) + '.' + str(code_item)
                undodict[code] = item.code[:-1]
                item.code = code
            else: 
                code_subitem = item.suborder + 1
                # If only one category reduce level of item numbering
                if len(code_cat_dict) == 1:
                    code = str(code_item) + '.' + str(code_subitem)
                else:
                    code = str(code_cat) + '.' + str(code_item) + '.' + str(code_subitem)
                undodict[code] = item.code[:-1]
                item.code = code
                
            item.save()
        
        yield "Assign automatic item numbers"
        
        # Change all items to prevent uniqueness errors
        ScheduleTable.update(code = ScheduleTable.code.concat('_')).execute()

        items = ScheduleTable.select()
        for item in items:
            mod_code = item.code[:-1]
            if mod_code in undodict:
                item.code = undodict[mod_code]
                item.save()
        
    def get_next_item_code(self, near_item_code=None, nextlevel=False, shift=0):
        if near_item_code:
            if nextlevel:
                new_code = near_item_code + '.' + str(1+shift)
                if not ScheduleTable.select().where(ScheduleTable.code == new_code).exists():
                    return new_code
            else:
                parsed = misc.human_code(near_item_code)
                if type(parsed[-1]) is int:
                    new_code_parsed = parsed[:-1] + [parsed[-1]+ (1+shift)]
                    new_code = ''
                    for part in new_code_parsed:
                        new_code = new_code + str(part)
                    if not ScheduleTable.select().where(ScheduleTable.code == new_code).exists():
                        return new_code
        
        # Fall back
        
        sch_items = ScheduleTable.select(ScheduleTable.code).where(ScheduleTable.code.startswith('_'))
        code_list = []
        
        # If fall through
        if near_item_code:
            shift = 0
        
        # Add exisitng default items
        for sch in sch_items:
            split_up = misc.human_code(sch.code)
            if len(split_up) == 2 and split_up[0] == '_' and type(split_up[-1]) is int:
                code_list.append(split_up)
                
        if code_list:
            last_code = sorted(code_list)[-1]
            if type(last_code[-1]) is int:
                new_code = '_' + str(int(last_code[-1])+1+shift)
            else:
                new_code = '_' + str(1+shift)
        else:
            new_code = '_' + str(1+shift)
        return new_code
        
    def get_new_schedule_category_name(self):
        categories =  ScheduleCategoryTable.select().where(ScheduleCategoryTable.description.startswith('_CATEGORY'))
        
        cat_list = []
        for category in categories:
            cat_list.append(misc.human_code(category.description))
            
        if categories:
            last_code = sorted(cat_list)[-1]
            if type(last_code[-1]) is int:
                new_code = '_CATEGORY' + str(last_code[-1]+1)
            else:
                new_code = '_CATEGORY1'
        else:
            new_code = '_CATEGORY1'
        return new_code
        
    ## Data correction functions
    
    @database.atomic()
    def reorder_items(self):
        """Performs reordering of all items in database to correct any insertion errors"""
        
        # Schedule items
        categories = ScheduleCategoryTable.select().order_by(ScheduleCategoryTable.order)
        for cat_id, category in enumerate(categories):
            category.order = cat_id
            items = ScheduleTable.select().where((ScheduleTable.category == category.id) & (ScheduleTable.parent == None)).order_by(ScheduleTable.order)
            category.save()
            for item_id, item in enumerate(items):
                item.order = item_id
                item.suborder = None
                item.save()
                children = ScheduleTable.select().where(ScheduleTable.parent == item.id).order_by(ScheduleTable.suborder)
                for child_id, child in enumerate(children):
                    child.order = item_id
                    child.suborder = child_id
                    child.save()
                    
        # Resource items
        categories = ResourceCategoryTable.select().order_by(ResourceCategoryTable.order)
        for cat_id, category in enumerate(categories):
            category.order = cat_id
            category.save()
            items = ResourceTable.select().where(ResourceTable.category == category.id).order_by(ResourceTable.order)
            for item_id, item in enumerate(items):
                item.order = item_id
                item.save()
                
    
    ## Export items

    def export_sch_spreadsheet(self, spreadsheet):
        sch_table = self.get_item_table()
        proj_name = self.get_project_settings()['project_name']

        # Header
        spreadsheet.add_merged_cell('SCHEDULE OF RATES', width=7, bold=True)
        rows = [[None]]
        spreadsheet.append_data(rows)
        spreadsheet.add_merged_cell('Name of Work: ' + proj_name, width=6, start_column=2, bold=True, horizontal='left')        
        rows = [[None],
                ['Sl.No.', 'Description', 'Unit', 'Rate', 'Qty','Amount', 'Remarks'],
                [None]]
        spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal='center')
        s_row = 8
        
        # Insert data
        for category, items in sch_table.items():
            # Add category item
            rows = [[None, category]]
            spreadsheet.append_data(rows, bold=True)
            s_row = s_row + 1
            # Set data of 1st level items
            for code, item_list in items.items():
                item = item_list[0]
                item_desc = item[1]
                item_unit = item[2]
                item_colour = item[6]
                
                # If item has multiple lines split up lines
                item_desc_parts = item_desc.split('\n')
                if len(item_desc_parts) > 1:
                    for part in item_desc_parts[0:-1]:
                        item_row = [code, part, None, None, None, None, None]
                        code = None
                        spreadsheet.append_data([item_row], fill=item_colour)
                        spreadsheet.set_style(s_row, 1, horizontal='center', vertical='top')
                        s_row = s_row + 1
                    item_desc = item_desc_parts[-1]
                    
                if item_unit == '':
                    item_rate = None
                    item_qty = None
                    item_amount = None
                else:
                    item_rate = item[3]
                    item_qty = item[4]
                    item_amount = '=ROUND(D' + str(s_row) + '*E' + str(s_row) + ",2)"
                item_remarks = item[5]
                    
                item_row = [code, item_desc, item_unit, item_rate, item_qty, item_amount, item_remarks]
                spreadsheet.append_data([item_row], fill=item_colour)
                spreadsheet.set_style(s_row, 1, horizontal='center', vertical='top')
                s_row = s_row + 1
                # Set data of 2nd level items
                for sub_item in item_list[1]:
                    code = sub_item[0]
                    desc = sub_item[1]
                    unit = sub_item[2]
                    rate = sub_item[3]
                    qty = sub_item[4]
                    remarks = sub_item[5]
                    colour = sub_item[6]
                    
                    # If item has multiple lines split up lines
                    item_desc_parts = desc.split('\n')
                    if len(item_desc_parts) > 1:
                        for part in item_desc_parts[0:-1]:
                            item_row = [code, part, None, None, None, None, None]
                            code = None
                            spreadsheet.append_data([item_row], fill=colour)
                            spreadsheet.set_style(s_row, 1, horizontal='center', vertical='top')
                            s_row = s_row + 1
                        desc = item_desc_parts[-1]
                        
                    amount = '=ROUND(D' + str(s_row) + '*E' + str(s_row) + ",2)"
                        
                    row = [code, desc, unit, rate, qty, amount, remarks]
                    spreadsheet.append_data([row], fill=colour)
                    spreadsheet.set_style(s_row, 1, horizontal='center', vertical='top')
                    s_row = s_row + 1
        # Add sum of amount
        amount = '=ROUND(SUM(F7:F' + str(s_row) + '),2)'
        rows = [[None],[None,'TOTAL',None,None,None,amount]]
        spreadsheet.append_data(rows, bold=True)
        
        # General formating
        spreadsheet.set_title('Schedule')
        spreadsheet.set_column_widths([10,50,10,10,10,15,15])
        spreadsheet.set_page_settings(font='Georgia')
        log.info('ScheduleDatabase - export_sch_spreadsheet - Schedule exported')
        
    def export_res_spreadsheet(self, spreadsheet):
        spreadsheet.new_sheet()
        spreadsheet.set_title('Resources')
        
        res_table = self.get_resource_table()

        # Header
        spreadsheet.add_merged_cell('SCHEDULE OF RESOURCES', width=8, bold=True)
        rows = [[None],
                ['Sl.No.', 'Description', 'Unit', 'Rate', 'Tax','Discount', 'Reference', 'Category'],
                [None]]
        spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal='center')
        s_row = 6
        
        # Insert data
        for category, items in res_table.items():
            # Add category item
            rows = [[None, category]]
            spreadsheet.append_data(rows, bold=True)
            s_row = s_row + 1

            # Set data of resource items
            for code, item in items.items():
                item_row = item + [category]
                spreadsheet.append_data([item_row])
                spreadsheet.set_style(s_row, 1, horizontal='center', vertical='top')
                s_row = s_row + 1
        
        # General formating
        spreadsheet.set_column_widths([10,40,10,10,10,15,25,25])
        spreadsheet.set_page_settings(font='Georgia')
        log.info('ScheduleDatabase - export_res_spreadsheet - Schedule exported')

    def export_ana_item_spreadsheet(self, code, spreadsheet, parent=None):
        sch_item = self.get_item(code)
        if sch_item.ana_items:
            s_row = spreadsheet.length() + 1

            # If parent item is there fill in code and decription
            if parent:
                [parent_code, item_desc] = parent
                spreadsheet.add_merged_cell(item_desc, width=5, start_column=2, horizontal='left')
                spreadsheet[s_row,1] = parent_code
                spreadsheet.set_style(s_row,1,horizontal='center', bold=True)
                s_row = s_row + 1
                
            # Add item number and description
            item_description = sch_item.description
            spreadsheet.add_merged_cell(item_description, width=5, start_column=2, horizontal='left')
            spreadsheet[s_row,1] = code
            spreadsheet.set_style(s_row, 1, horizontal='center', bold=True)
            s_row = s_row + 1
            # Add item ana_remarks
            spreadsheet.add_merged_cell(sch_item.ana_remarks, width=5, start_column=2, horizontal='left')
            s_row = s_row + 1
            # Add header row
            header = [['Code', 'Description', 'Unit', 'Rate', 'Qty', 'Amount']]
            spreadsheet.append_data(header, bold=True, horizontal='center')
            s_row = s_row + 1

            sum_item = '0'
            sum_total = '0'
            for slno, item in enumerate(sch_item.ana_items):

                if item['itemtype'] == ScheduleItemModel.ANA_GROUP:
                    # Add analysis group
                    code = item['code']
                    description = item['description']
                    spreadsheet.append_data([[code, description]], bold=True)
                    s_row_start = s_row = s_row + 1
                    # Add resources
                    for resource_item in item['resource_list']:
                        res_code = resource_item[0]
                        qty = resource_item[1]
                        remarks = resource_item[2]
                        resource = sch_item.resources[resource_item[0]]
                        res_description = resource.description
                        res_unit = resource.unit
                        rate = resource.rate
                        vat = resource.vat
                        discount = resource.discount
                        if vat or discount:
                            rate_formula = "=ROUND(" + str(rate) + "*" + str(1+vat/100) + "*" + str(1-discount/100) + ",2)"
                        else:
                            rate_formula = rate
                        amount = '=ROUND(D' + str(s_row) + '*E' + str(s_row) + ',2)'
                        
                        rate_desc = 'Basic rate ' + str(rate)
                        ref_desc = ' [' + resource.reference + ']' if resource.reference else ''
                        vat_desc = ' + Tax @' + str(vat) + '%' if vat else ''
                        discount_desc = ' - Discount @' + str(discount) + '%' if discount else ''
                        if vat or discount or ref_desc:
                            net_description = res_description + '\n(' + rate_desc + \
                                          ref_desc + vat_desc + discount_desc + ')'
                        else:
                            net_description = res_description
                        
                        row = [res_code, net_description, res_unit, rate_formula, qty, amount]
                        spreadsheet.append_data([row])
                        spreadsheet.set_style(s_row, 1, horizontal='center')
                        s_row = s_row + 1
                        if remarks:
                            spreadsheet.append_data([[None," " + remarks]], italic=True)
                            s_row = s_row + 1
                    total_desc = ('TOTAL of ' + description) if code is None else 'TOTAL of ' + code
                    total_total = '=SUM(F' + str(s_row_start) + ':F' + str(s_row-1) + ')'
                    spreadsheet.append_data([[None,total_desc,None,None,None,total_total]])
                    sum_item = 'F' + str(s_row)
                    sum_total = (sum_total + '+' + sum_item) if sum_total != '0' else sum_item
                    s_row = s_row + 1

                elif item['itemtype'] == ScheduleItemModel.ANA_SUM:
                    desc = item['description']
                    spreadsheet.append_data([[None, desc, None, None, None, '='+sum_total]])
                    sum_item = sum_total = 'F' + str(s_row)
                    s_row = s_row + 1

                elif item['itemtype'] == ScheduleItemModel.ANA_WEIGHT:
                    desc = item['description']
                    value = item['value']
                    total = '=ROUND(' + str(value) + '*' + sum_item + ',2)'
                    spreadsheet.append_data([[None, desc, None, None, None, total]])
                    sum_total = sum_total + '+ F' + str(s_row)
                    s_row = s_row + 1

                elif item['itemtype'] == ScheduleItemModel.ANA_TIMES:
                    desc = item['description']
                    value = item['value']
                    total = '=ROUND(' + str(value) + '*' + sum_item + ',2)'
                    spreadsheet.append_data([[None, desc, None, None, None, total]])
                    sum_item = sum_total = 'F' + str(s_row)
                    s_row = s_row + 1

                elif item['itemtype'] == ScheduleItemModel.ANA_ROUND:
                    desc = item['description']
                    value = item['value']
                    if int(value) == value:
                        total = '=ROUND(' + sum_total + ',' + str(value) + ')'
                    else:
                        precision = int(value)
                        base = int((value - int(value))*10)
                        total = '=MROUND(' + sum_total + ',' + str(base*10**-precision) + ')'
                    spreadsheet.append_data([[None, desc, None, None, None, total]], bold=True)
                    sum_item = sum_total = 'F' + str(s_row)
                    s_row = s_row + 1

            spreadsheet.append_data([[None],[None]])

    def export_ana_spreadsheet(self, spreadsheet, progress, range_progress):
        sch_table = self.get_item_table()
        spreadsheet.new_sheet()
        spreadsheet.set_title('Analysis')

        # Header
        spreadsheet.add_merged_cell('ANALYSIS OF RATES', width=6, bold=True)
        rows = [[None]]
        spreadsheet.append_data(rows)
        # Current row in spreadsheet
        s_row = 4
        # Total items for progress updation
        total_items = 0
        cur_item = 0
        for category in sch_table:
            total_items = total_items + len(sch_table[category])

        # Insert data
        for category, items in sch_table.items():
            # Add category item
            rows = [[None, category],[None]]
            spreadsheet.append_data(rows, bold=True)
            s_row = s_row + 2
            # Set data of 1st level items
            for code, item_list in items.items():
                item = item_list[0]
                item_desc = item[1]
                item_unit = item[2]
                # If parent item
                if item_unit == '':
                    # Set data of 2nd level items
                    for sub_item in item_list[1]:
                        code2 = sub_item[0]
                        self.export_ana_item_spreadsheet(code2, spreadsheet, [code, item_desc])
                        s_row = spreadsheet.length() + 1
                # If regular item
                else:
                    self.export_ana_item_spreadsheet(code, spreadsheet)
                    s_row = spreadsheet.length() + 1
                progress.set_fraction(range_progress[0] + (range_progress[1]-range_progress[0])*cur_item/total_items)
                cur_item = cur_item + 1
            log.info('ScheduleDatabase - export_ana_spreadsheet - Analysis exported - ' + category)

        spreadsheet.set_column_widths([10, 50, 10, 15, 10, 15])
        spreadsheet.set_page_settings(font='Georgia')
        log.info('ScheduleDatabase - export_ana_spreadsheet - Analysis exported')
        
            
    def export_res_usage_spreadsheet(self, spreadsheet): 
        cat_res_items = self.get_res_usage()
        spreadsheet.new_sheet()
        spreadsheet.set_title('Res Usage')

        # Header
        spreadsheet.add_merged_cell('WORK RESOURCE USAGE', width=6, bold=True)
        rows = [[None],
                ['Code', 'Description', 'Unit', 'Rate', 'Qty', 'Amount'],
                [None]]
        spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal='center')
        s_row = 6
        
        for category, res_list_item in cat_res_items.items():
            # Add category item
            rows = [[None, category]]
            spreadsheet.append_data(rows, bold=True)
            s_row = s_row + 1
            for code, item in sorted(res_list_item.items()):
                description = item[1]
                unit = item[2]
                qty = item[3]
                basicrate = Currency(item[4])
                vat = Currency(item[5]) if item[5] is not None else Decimal(0)
                discount = Currency(item[6]) if item[6] is not None else Decimal(0)
                rate = Currency(basicrate*(1+vat/100)*(1-discount/100))
                amount_formula = '=ROUND(D' + str(s_row) + '*E' + str(s_row) + ',2)'
                rows = [[code, description, unit, rate, qty, amount_formula]]
                spreadsheet.append_data(rows)
                s_row = s_row + 1
            
        spreadsheet.set_column_widths([10, 50, 10, 10, 15, 15])
        spreadsheet.set_page_settings(font='Georgia')
        
        log.info('ScheduleDatabase - export_res_usage_spreadsheet - Resource Usage exported')
        
