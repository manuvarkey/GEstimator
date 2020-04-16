#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  measurement.py
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

from gi.repository import Gtk, Gdk, GLib
import copy, logging

# local files import
from .. import misc, meas_templates

# Get logger object
log = logging.getLogger()


class Measurement:
    """Stores a Measurement groups"""
    def __init__(self, model = None):
        if model is not None:
            self.caption = model[0]
            self.items = []
            class_list = ['MeasurementItemHeading',
                        'MeasurementItemCustom',
                        'MeasurementItemAbstract']
            for item_model in model[1]:
                if item_model[0] in class_list:
                    item_type = globals()[item_model[0]]
                    item = item_type()
                    item.set_model(item_model)
                    self.items.append(item)
        else:
            self.caption = ''
            self.items = []

    def append_item(self,item):
        self.items.append(item)

    def insert_item(self,index,item):
        self.items.insert(index,item)

    def remove_item(self,index):
        del(self.items[index])

    def __setitem__(self, index, value):
        self.items[index] = value

    def __getitem__(self, index):
        return self.items[index]

    def set_caption(self,caption):
        self.caption = caption

    def get_caption(self):
        return self.caption

    def length(self):
        return len(self.items)

    def get_model(self, clean=False):
        """Get data model

            Arguments:
                clean: Removes static items if True
        """
        items_model = []
        for item in self.items:
            items_model.append(item.get_model(clean))
        return ['Measurement', [self.caption, items_model]]

    def get_net_measurement(self):
        # Fill in values from measurement items
        self.paths = dict()
        self.qtys = dict()
        self.sums = dict()
        for slno, item in enumerate(self.items):
            if not isinstance(item, MeasurementItemHeading):
                for itemno, qty in zip(item.itemnos, item.get_total()):
                    if itemno not in self.paths:
                        self.paths[itemno] = []
                        self.qtys[itemno] = []
                        self.sums[itemno] = 0
                    self.paths[itemno].append(slno)
                    self.qtys[itemno].append(qty)
                    self.sums[itemno] += qty
        return (self.paths, self.qtys, self.sums)

    def set_model(self, model):
        """Set data model"""
        if model[0] == 'Measurement':
            self.__init__(model[1])

    def get_spreadsheet_buffer(self, schedule, codes, start_row):
        spreadsheet = misc.Spreadsheet()
        row = start_row
        # Set datas of children
        for slno, item in enumerate(self.items):
            item_sheet = item.get_spreadsheet_buffer([slno+1], schedule, codes, row)
            spreadsheet.append(item_sheet)
            row = row + item_sheet.length()
        return spreadsheet

    def clear(self):
        self.items = []

    def get_text(self):
        return "<b>Measurement captioned." + misc.clean_markup(self.caption) + "</b>"

    def get_tooltip(self):
        return None

    def print_item(self):
        print("  " + "Measurement captioned " + self.caption)
        for item in self.items:
            item.print_item()

class MeasurementItem:
    """Base class for storing Measurement items"""
    def __init__(self, itemnos=None, records=None, remark="", item_remarks=None):
        if itemnos is None:
            itemnos = []
        if records is None:
            records = []
        if item_remarks is None:
            item_remarks = []

        self.itemnos = itemnos
        self.records = records
        self.remark = remark
        self.item_remarks = item_remarks

    def set_item(self,index,itemno):
        self.itemnos[index] = itemno

    def get_item(self,index):
        return self.itemnos[index]

    def append_record(self,record):
        self.records.append(record)

    def insert_record(self,index,record):
        self.records.insert(index,record)

    def remove_record(self,index):
        del(self.records[index])

    def __setitem__(self, index, value):
        self.records[index] = value

    def __getitem__(self, index):
        return self.records[index]

    def set_remark(self,remark):
        self.remark = remark

    def get_remark(self):
        return self.remark

    def length(self):
        return len(self.records)

    def clear(self):
        self.itemnos = []
        self.records = []
        self.remark = ''
        self.item_remarks = []

class MeasurementItemHeading(MeasurementItem):
    """Stores an item heading"""
    def __init__(self, model=None):
        if model is not None:
            MeasurementItem.__init__(self,remark=model[0])
        else:
            MeasurementItem.__init__(self)

    def get_model(self, clean=False):
        """Get data model

            Arguments:
                clean: Dummy variable
        """
        model = ['MeasurementItemHeading', [self.remark]]
        return model

    def set_model(self, model):
        """Set data model"""
        if model[0] == 'MeasurementItemHeading':
            self.__init__(model[1])

    def get_spreadsheet_buffer(self, path, schedule, codes, row):
        spreadsheet = misc.Spreadsheet()
        spreadsheet.append_data([[str(path), self.remark], [None]], bold=True, wrap_text=True)
        return spreadsheet

    def get_text(self):
        heading = self.remark.splitlines()[0]
        return "<b>" + misc.clean_markup(heading) + "</b>"

    def get_tooltip(self):
        return None

    def print_item(self):
        print("    " + self.remark)

class RecordCustom:
    """An individual record of a MeasurementItemCustom"""
    def __init__(self, items, cust_funcs, total_func, columntypes):
        self.data_string = items
        self.data = []
        # Populate Data
        for x,columntype in zip(self.data_string,columntypes):
            if columntype not in [misc.MEAS_DESC, misc.MEAS_CUST]:
                try:
                    num = eval(x)
                    self.data.append(num)
                except:
                    self.data.append(0)
            else:
                self.data.append(0)
        self.cust_funcs = cust_funcs
        self.total_func = total_func
        self.columntypes = columntypes
        self.total = self.find_total()

    def get_model(self):
        """Get data model"""
        return self.data_string

    def get_model_rendered(self, row=None):
        """Get data model with results of custom functions included for rendering"""
        item = self.get_model()
        rendered_item = []
        for item_elem, columntype, render_func in zip(item, self.columntypes, self.cust_funcs):
            try:
                if item_elem != "" or columntype == misc.MEAS_CUST:
                    if columntype == misc.MEAS_CUST:
                        try:
                            # Try for numerical values
                            value = float(render_func(item, row))
                        except:
                            # If evaluation fails gracefully fallback to string
                            value = render_func(item, row)
                        rendered_item.append(value)
                    if columntype == misc.MEAS_DESC:
                        rendered_item.append(item_elem)
                    elif columntype == misc.MEAS_NO:
                        value = int(eval(item_elem)) if item_elem not in ['0','0.0'] else 0
                        rendered_item.append(value)
                    elif columntype == misc.MEAS_L:
                        value = round(eval(item_elem),3) if item_elem not in ['0','0.0'] else 0
                        rendered_item.append(value)
                else:
                    rendered_item.append(None)
            except TypeError:
                rendered_item.append(None)
                log.warning('RecordCustom - Wrong value loaded in item - ' + str(item_elem))
        return rendered_item

    def set_model(self, items, cust_funcs, total_func, columntypes):
        """Set data model"""
        self.__init__(items, cust_funcs, total_func, columntypes)

    def find_total(self):
        return self.total_func(self.data)

    def find_custom(self,index):
        return self.cust_funcs[index](self.data)

    def print_item(self):
        print("      " + str([self.data_string,self.total]))


class MeasurementItemCustom(MeasurementItem):
    """Stores a custom record set [As per plugin loaded]"""
    def __init__(self, data = None, plugin=None):
        self.name = ''
        self.itemtype = None
        self.itemnos_mask = []
        self.captions = []
        self.columntypes = []
        self.cust_funcs = []
        self.total_func_item = None
        self.total_func = None
        # For user data support
        self.captions_udata = []
        self.columntypes_udata = []
        self.user_data = None
        self.dimensions = None

        # Read description from file
        if plugin is not None:
            try:
                module = getattr(meas_templates, plugin)
                self.custom_object = module.CustomItem()
                self.name = self.custom_object.name
                self.itemtype = plugin
                self.itemnos_mask = self.custom_object.itemnos_mask
                self.captions = self.custom_object.captions
                self.columntypes = self.custom_object.columntypes
                self.cust_funcs = self.custom_object.cust_funcs
                self.total_func_item = self.custom_object.total_func_item
                self.total_func = self.custom_object.total_func
                # For user data support
                self.captions_udata = self.custom_object.captions_udata
                self.columntypes_udata = self.custom_object.columntypes_udata
                self.user_data = self.custom_object.user_data_default
                self.dimensions = self.custom_object.dimensions
            except ImportError:
                log.error('Error Loading plugin - MeasurementItemCustom - ' + str(plugin))

            if data != None:
                itemnos = data[0]
                records = []
                for item_model in data[1]:
                    item = RecordCustom(item_model, self.cust_funcs,
                                        self.total_func_item, self.columntypes)
                    records.append(item)
                remark = data[2]
                item_remarks = data[3]
                self.user_data = data[4]
                MeasurementItem.__init__(self, itemnos, records, remark, item_remarks)
            else:
                MeasurementItem.__init__(self, [None]*self.item_width(), [],
                                        '', ['']*self.item_width())
        else:
            MeasurementItem.__init__(self)

    def model_width(self):
        """Returns number of columns being measured"""
        return len(self.columntypes)

    def item_width(self):
        """Returns number of itemnos being measured"""
        return len(self.itemnos_mask)

    def get_model(self, clean=False):
        """Get data model

            Arguments:
                clean: Dummy variable
        """
        item_schedule = []
        for item in self.records:
            item_schedule.append(item.get_model())
        data = [self.itemnos, item_schedule, self.remark, self.item_remarks,
                self.user_data, self.itemtype]
        return ['MeasurementItemCustom', data]

    def set_model(self, model):
        """Set data model"""
        if model[0] == 'MeasurementItemCustom':
            self.clear()
            self.__init__(model[1], model[1][5])

    def get_spreadsheet_buffer(self, path, schedule, codes, s_row):
        spreadsheet = misc.Spreadsheet()
        row = 1
        # Item no and description
        for slno, key in enumerate(self.itemnos):
            if key in codes.keys():
                itemno = codes[key]
            else:
                itemno = None
            if itemno is not None:
                spreadsheet.append_data([[str(path), 'Item No:' + itemno, self.item_remarks[slno]]], bold=True, wrap_text=True)
                spreadsheet.append_data([[None, schedule[itemno][1]]])
                row = row + 2
        # Remarks columns
        if self.remark != '':
            spreadsheet.append_data([[None, 'Remarks: ' + self.remark]], bold=True)
            row = row + 1
        # Data rows
        spreadsheet.append_data([[None], [None] + self.captions], bold=True)
        row = row + 1
        for slno, record in enumerate(self.records,1):
            values = record.get_model_rendered(slno)
            spreadsheet.append_data([[slno] + values])
            row = row + 1
        # User data
        if self.captions_udata:
            spreadsheet.append_data([[None], [None, 'User Data Captions'] + self.captions_udata], bold=True)
            spreadsheet.append_data([[None, 'User Datas'] + self.user_data])
            row = row + 2
        # Total values
        spreadsheet.append_data([[None, 'TOTAL'] + self.get_total(), [None]], bold=True)
        row = row + 2
        return spreadsheet

    def print_item(self):
        print("    Item No." + str(self.itemnos))
        for i in range(self.length()):
            self[i].print_item()
        print("    " + "Total: " + str(self.get_total()))

    def get_total(self):
        if self.total_func is not None:
            return self.total_func(self.records,self.user_data)
        else:
            return []

    def get_text(self):
        total = self.get_total()
        return self.name + ": "+ self.remark + ", #" + \
            str(self.length()) + ", Σ " + str(total)

    def get_tooltip(self):
        if self.remark != "":
            return "Remark: " + self.remark
        else:
            return None

