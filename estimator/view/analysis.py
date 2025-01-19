#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  analysis.py
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

import pickle, codecs, os.path, copy, logging
from decimal import Decimal

from gi.repository import Gtk, Gdk, GLib, Pango

# local files import
from . import resource
from .. import misc, data, undo
from ..undo import undoable
from .cellrenderercustomtext import CellRendererTextView

# Setup logger object
log = logging.getLogger(__name__)


class AnalysisView:
    """Implements a view for display and manipulation of measurement items over a treeview"""

    # Callback functions

    def on_key_press_treeview(self, widget, event, treeview):
        """Handle keypress event"""
        keyname = event.get_keyval()[1]
        state = event.get_state()
        shift_pressed = bool(state & Gdk.ModifierType.SHIFT_MASK)

        if keyname in [Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Escape]:  # unselect all
            self.tree.get_selection().unselect_all()
            return

        if bool(state & Gdk.ModifierType.CONTROL_MASK):
            if keyname in (Gdk.KEY_c, Gdk.KEY_C):
                self.on_copy()
            elif keyname in (Gdk.KEY_v, Gdk.KEY_V):
                self.on_paste()
            return

        path, col = treeview.get_cursor()
        if path != None:
            columns = [c for c in treeview.get_columns()]
            colnum = columns.index(col)
            rownum = path.get_indices()[0]
            store = treeview.get_model()
            if col in columns:
                if keyname in [Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab]:
                    if shift_pressed == 1:
                        # Search over editable states
                        for row in range(rownum,-1,-1):
                            # Determine starting column
                            # For same row
                            if row == rownum:
                                end = (colnum-1)+9
                            # For different row
                            else:
                                end = 15
                            for col in range(end,8,-1):
                                if self.store[row][col] == True:
                                    prev_column = columns[col-9]
                                    path = Gtk.TreePath.new_from_indices([row])
                                    treeview.scroll_to_cell(path, prev_column, False)
                                    if row == rownum:
                                        GLib.idle_add(treeview.set_cursor, path, prev_column, True)
                                    else:
                                        GLib.timeout_add(200, treeview.set_cursor, path, prev_column, True)
                                    return
                    else:
                        # Search over editable states
                        for row in range(rownum,len(store)):
                            # Determine starting column
                            # For same row
                            if row == rownum:
                                start = (colnum+1)+9
                            # For different row
                            else:
                                start = 9
                            for col in range(start, 15):
                                if self.store[row][col] == True:
                                    next_column = columns[col-9]
                                    path = Gtk.TreePath.new_from_indices([row])
                                    treeview.scroll_to_cell(path, next_column, False)
                                    if row == rownum:
                                        GLib.idle_add(treeview.set_cursor, path, next_column, True)
                                    else:
                                        GLib.timeout_add(200, treeview.set_cursor, path, next_column, True)
                                    return

    def on_wrap_column_resized(self, column, pspec, cell):
        """ Automatically adjust wrapwidth to column width"""

        width = column.get_width()
        oldwidth = cell.props.wrap_width

        if width > 0 and width != oldwidth:
            cell.props.wrap_width = width
            # Force redraw of treeview
            GLib.idle_add(column.queue_resize)

    def on_undo(self):
        """Undo action from stack"""
        log.info('AnalysisView - Undo:' + str(self.stack.undotext()))
        self.stack.undo()

    def on_redo(self):
        """Redo action from stack"""
        log.info('AnalysisView - Redo:' + str(self.stack.redotext()))
        self.stack.redo()

    def on_copy(self):
        """Copy selected row to clipboard"""

        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0: # if selection exists
            test_string = "AnalysisView"

            items = []
            [model, paths] = selection.get_selected_rows()
            for pathiter in paths:
                row = pathiter.get_indices()[0]
                path = eval(self.store[pathiter][8])
                if None not in path:
                    item = self.model.get_item(path, deep=False)
                    items.append(item)
            if items:
                text = codecs.encode(pickle.dumps([test_string, self.instance_code_callback(), items]), "base64").decode() # dump item as text
                self.clipboard.set_text(text,-1) # push to clipboard
                log.info('AnalysisView - on_copy - Item copied to clipboard - ' + str(path))
                return
        # if no selection
        log.warning("AnalysisView - copy_selection - No items selected to copy")

    def on_paste(self):
        """Paste copied item at selected row"""

        text = self.clipboard.wait_for_text() # get text from clipboard
        if text != None:
            test_string = "AnalysisView"
            try:
                itemlist = pickle.loads(codecs.decode(text.encode(), "base64"))  # recover item from string
                if itemlist[0] == test_string:
                    model_copy = copy.deepcopy(self.model)

                    check_instance_code = itemlist[1]
                    items = itemlist[2]
                    selection = self.tree.get_selection()

                    # If selection exists
                    if selection.count_selected_rows() != 0:
                        [model, paths] = selection.get_selected_rows()
                        row = paths[0].get_indices()
                        path = eval(self.store[paths[0]][8])
                    # Else add at top
                    else:
                        path = [-1]

                    insertion_path = path
                    for item in items:

                        if item[0] == 'ana_item':
                            insertion_path[0] = insertion_path[0] + 1
                            model_copy.insert_item(item[1], insertion_path)

                        elif item[0] == 'resource_item' and model_copy.ana_items[insertion_path[0]]['itemtype'] == data.schedule.ScheduleItemModel.ANA_GROUP:

                            if len(insertion_path) == 1:
                                insertion_path = [insertion_path[0], 0]
                            else:
                                insertion_path = [insertion_path[0], insertion_path[1]+1]

                            # If resource not a library item and from different document, get modified code
                            if check_instance_code != self.instance_code_callback() and len((item[1][0]).split(':')) == 1:
                                item[1][0] = check_instance_code + '.' + item[1][0]
                                item[2].code = item[1][0]

                            code = model_copy.insert_item(item[1], insertion_path)

                            # Add resource if resource does not exist in model
                            if code not in model_copy.resources:
                                model_copy.resources[code] = item[2]
                                # Set flag
                                self.res_needs_refresh = True
                                # Add item to custom items
                                self.custom_items.append(code)

                    self.modify_model(model_copy, "Paste items at path:'{}'".format(path))
                    log.info('AnalysisView - on_paste - Item pasted at - ' + str(path))
                    return
            except:
                log.warning('AnalysisView - paste_at_selection - No valid data in clipboard')
        else:
            log.warning('AnalysisView - paste_at_selection - No text in clipboard')

    def cell_renderer(self, cell, pathiter, newtext, column):
        """Treeview cell renderer for editable text field

            User Data:
                column: column in ListStore being edited
        """
        model_copy = copy.deepcopy(self.model)
        path = eval(self.store[pathiter][8])

        try:
            evaluated = round(eval(newtext), 6)
        except:
            evaluated = 0

        item = model_copy.ana_items[path[0]]
        if item['itemtype'] == data.schedule.ScheduleItemModel.ANA_GROUP:
            if len(path) == 1:
                if column == 0:
                    if item['code'] == newtext:
                        return
                    item['code'] = newtext
                elif column == 1:
                    if item['description'] == newtext:
                        return
                    item['description'] = newtext
            elif len(path) == 2:
                res_item = item['resource_list'][path[1]]
                if column == 0:
                    res = self.database.get_resource(newtext)
                    if res:
                        if res_item[0] == newtext:
                            return
                        res_item[0] = newtext
                        model_copy.resources[newtext] = res
                elif column == 2:
                    if res_item[2] == newtext:
                        return
                    res_item[2] = newtext
                elif column == 4:
                    if res_item[1] == evaluated:
                        return
                    res_item[1] = evaluated
        elif item['itemtype'] == data.schedule.ScheduleItemModel.ANA_SUM:
            if column == 1:
                if item['description'] == newtext:
                    return
                item['description'] = newtext
        elif item['itemtype'] in [data.schedule.ScheduleItemModel.ANA_WEIGHT,
                                   data.schedule.ScheduleItemModel.ANA_TIMES,
                                   data.schedule.ScheduleItemModel.ANA_ROUND]:
            if column == 1:
                if item['description'] == newtext:
                    return
                item['description'] = newtext
            elif column == 4:
                if item['value'] == evaluated:
                    return
                item['value'] = evaluated

        self.modify_model(model_copy, "Change data item at path:'{}' and column:'{}'".format(path, column))

    def add_res_library(self, res_select_dialog):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            if path is not None and model_copy.ana_items[path[0]]['itemtype'] == data.schedule.ScheduleItemModel.ANA_GROUP:
                # Show user data dialog
                res_models = res_select_dialog.run()

                # Add data on success
                if res_models:
                    for res_model in reversed(res_models):
                        code = res_model.code
                        res_item = [code, Decimal(0), '']

                        resource_db = self.database.get_resource(code)
                        # Add received resource model if item exist in database
                        if resource_db:
                             model_copy.resources[code] = resource_db
                        # Else add the returned resource
                        else:
                            model_copy.resources[code] = res_model

                        if len(path) == 1:
                            model_copy.add_ana_res(res_item, path[0], 0)
                        elif len(path) == 2:
                            if path[1] is not None:
                                model_copy.add_ana_res(res_item, path[0], path[1]+1)
                            else:
                                model_copy.add_ana_res(res_item, path[0])
                        # Add item to custom items
                        self.custom_items.append(code)
                    self.modify_model(model_copy, "Add resource from library at path:'{}' ".format(path))
                    # Set flag
                    self.res_needs_refresh = True
                    # Set selection
                    if len(path) == 1:
                        selection_path = [path[0], 0]
                    elif len(path) == 2:
                        if path[1] is not None:
                            selection_path = [path[0], path[1]+1]
                        else:
                            selection_path = [path[0], None]
                    self.set_selection(selection_path)

    def add_res(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            if path is not None and model_copy.ana_items[path[0]]['itemtype'] == data.schedule.ScheduleItemModel.ANA_GROUP:
                # Setup resource data dialog
                resource_entry_dialog = resource.ResourceEntryDialog(self.parent, self.database, self.custom_items)
                # Run resource data dialog
                ret_code = resource_entry_dialog.run()

                if ret_code:
                    res = ret_code[1]
                    code = res.code
                    # Add resource item
                    res_item = [code, '0', '']
                    model_copy.resources[code] = res
                    if len(path) == 1:
                        model_copy.add_ana_res(res_item, path[0], 0)
                        selection_path = [path[0], 0]
                    elif len(path) == 2:
                        if path[1] is not None:
                            model_copy.add_ana_res(res_item, path[0], path[1]+1)
                            selection_path = [path[0], path[1]+1]
                        else:
                            model_copy.add_ana_res(res_item, path[0])
                            selection_path = [path[0], None]
                    self.modify_model(model_copy, "Add new resource at path:'{}' ".format(path))
                    # Set flag
                    self.res_needs_refresh = True
                    # Add item to custom items
                    self.custom_items.append(code)
                    self.set_selection(selection_path)

    def edit_res(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])

            if path is not None and len(path) == 2:
                res_item_model = model_copy.get_item(path)

                if res_item_model[0] == 'resource_item':
                    # Get current item
                    res = res_item_model[2]
                    # Setup resource data dialog
                    resource_entry_dialog = resource.ResourceEntryDialog(self.parent, self.database, self.custom_items, res)
                    # Run resource data dialog
                    ret_code = resource_entry_dialog.run()

                    if ret_code:
                        res = ret_code[1]
                        code = res.code
                        # Modify model
                        if code in self.custom_items:
                            model_copy.resources[code] = res
                            self.modify_model(model_copy, "Modify resource '{}' ".format(code))
                        else:
                            # Momemtarily change undo stack
                            stack_old = undo.stack()
                            undo.setstack(self.stack_old)
                            # Set main resource
                            res_mod_status = self.database.update_resource(code=code, res_model=res)
                            # Initialise saved undo/redo stack
                            undo.setstack(stack_old)

                            if res_mod_status:
                                # Update model
                                model_copy.resources[code] = res
                                self.modify_model(model_copy, "Modify main database resource '{}' ".format(code), undo_main_database=True)
                                # Set flag
                                self.res_needs_refresh = True

    def add_res_group(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            pos = path[0]+1 if path is not None else 0
        else:
            pos = 0

        model_copy.add_ana_group('RESOURCE', [], '', pos)
        self.modify_model(model_copy, "Add new resource group at row:'{}' ".format(pos))
        self.set_selection([pos])

    def add_sum(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            pos = path[0]+1 if path is not None else 0
        else:
            pos = 0

        model_copy.add_ana_sum('TOTAL', pos)
        self.modify_model(model_copy, "Add new sum item at row:'{}' ".format(pos))
        self.set_selection([pos])

    def add_weight(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            pos = path[0]+1 if path is not None else 0
        else:
            pos = 0

        model_copy.add_ana_weight('Add x @ x%', 0.01, pos)
        self.modify_model(model_copy, "Add new weight item at row:'{}' ".format(pos))
        self.set_selection([pos])

    def add_times(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            pos = path[0]+1 if path is not None else 0
        else:
            pos = 0

        model_copy.add_ana_times('Rate for unit item', 0.01, pos)
        self.modify_model(model_copy, "Add new times item at row:'{}' ".format(pos))
        self.set_selection([pos])

    def add_round(self):
        model_copy = copy.deepcopy(self.model)

        row = self.get_selected_row()
        if row:
            path = eval(self.store[row][8])
            pos = path[0]+1 if path is not None else 0
        else:
            pos = 0

        model_copy.add_ana_round('Say', 0, pos)
        self.modify_model(model_copy, "Add new round item at row:'{}' ".format(pos))
        self.set_selection([pos])

    def delete_selected_row(self):
        """Delete selected rows"""
        model_copy = copy.deepcopy(self.model)

        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            for pathiter in reversed(paths):
                path = pathiter.get_indices()
                item_path = eval(self.store[path][8])
                # Skip resource total item
                if None in item_path:
                    continue
                model_copy.delete_item(item_path)
            self.modify_model(model_copy, 'Delete items from analysis')

    # Class Methods

    @undoable
    def modify_model(self, newval, message, undo_main_database=False):
        oldmodel = self.model
        self.model = newval
        self.update_store()

        yield message
        # Undo main database
        if undo_main_database:
            self.stack_old.undo()
        # Undo action
        self.model = oldmodel
        self.update_store()

    def cell_editing_started(self, widget, editable, path, column):
        """Fill in text from schedule when schedule view column get edited

            User Data:
                column: column in ListStore being edited
        """
        editable.editor.connect("key-press-event", self.on_key_press_treeview, self.tree)

    def set_colour(self, path, color):
        """Sets the colour of item selected by path"""
        if len(path) == 1:
            path_formated = Gtk.TreePath.new_from_string(str(path[0]))
        elif len(path) == 2:
            path_formated = Gtk.TreePath.new_from_string(str(path[0]) + ':' + str(path[1]))
        elif len(path) == 3:
            path_formated = Gtk.TreePath.new_from_string(str(path[0]) + ':' + str(path[1]) + ':' + str(path[2]))
        else:
            return
        path_iter = self.store.get_iter(path_formated)
        self.store.set_value(path_iter, 7, color)

    def get_selected_row(self):
        # Get selection
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0:  # If selection exists
            [model, paths] = selection.get_selected_rows()
            return paths[0].get_indices()
        else:
            return None

    def set_selection(self, path=None):
        def search_func(model, path, iterator, data):
            code = data[0]
            if model[iterator][8] == code:
                data[1] = path
                return True

        data = [str(path), None]
        self.store.foreach(search_func, data)
        if data[1] is not None:
            self.tree.set_cursor(data[1])
            self.tree.scroll_to_cell(data[1], None)

    def update_store(self):
        """Update GUI of AnalysisView from data model while trying to preserve selection"""

        log.info('AnalysisView - update_store')

        C1 = lambda x : '<span color="#486581"><b>{x}</b></span>'.format(x=str(x))
        C2 = lambda x : '<span color="#c30101"><b>{x}</b></span>'.format(x=str(x))

        # Get selection
        selection = self.tree.get_selection()
        old_row = None
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            old_row = paths[0].get_indices()[0]

        # Update model
        self.model.evaluate_results()

        # Update analysis remarks
        if self.entry_analysis_remarks:
            if self.entry_analysis_remarks.get_text() == "" and self.model.ana_remarks is not None:
                self.entry_analysis_remarks.set_text(self.model.ana_remarks)
            else:
                self.model.ana_remarks = self.entry_analysis_remarks.get_text()

        # Update StoreView
        self.store.clear()
        for p1, (item, result) in enumerate(zip(self.model.ana_items, self.model.results)):
            if item['itemtype'] == data.schedule.ScheduleItemModel.ANA_GROUP:
                if item['code'] is None:
                    item_code = ''
                else:
                    item_code = item['code']
                item_code_ = '<b>' + misc.clean_markup(item_code) + '</b>'
                description_ = '<b>' + misc.clean_markup(item['description']) + '</b>'
                iter_item = self.store.append(None,[item_code_, description_, '', '', '', '', '', misc.MEAS_COLOR_NORMAL, str([p1]),
                                                    True,True,False,False,False,False,False])
                for p2, (res_item, result_res_item) in enumerate(zip(item['resource_list'], result)):
                    code = res_item[0]
                    qty = res_item[1]
                    remarks = res_item[2]
                    # Get resource from model
                    resource = self.model.resources[code]
                    description = resource.description
                    unit = resource.unit
                    rate = resource.rate
                    vat = resource.vat
                    discount = resource.discount
                    net_rate = result_res_item[0]
                    amount = result_res_item[1]

                    rate_desc = 'Basic rate ' + str(rate)
                    ref_desc = ' [' + resource.reference + ']' if resource.reference else ''
                    vat_desc = ' + Tax @' + str(vat) + '%' if vat else ''
                    discount_desc = ' - Discount @' + str(discount) + '%' if discount else ''
                    if vat or discount or ref_desc:
                        net_description = description + '\n(' + rate_desc + \
                                      ref_desc + vat_desc + discount_desc + ')'
                    else:
                        net_description = description
                    remarks_ = '' if remarks is None else misc.clean_markup(remarks)
                    iter_res_item = self.store.append(None,[code, misc.clean_markup(net_description), unit, str(qty), str(net_rate),
                                                                 str(amount), remarks_, misc.MEAS_COLOR_NORMAL, str([p1,p2]),
                                                                 True,False,True,False,True,False,False])
                amount = result[-1]
                group_total_desc = 'TOTAL of ' + item_code if item_code != '' else 'TOTAL of ' + item['description']
                iter_res_item = self.store.append(None,['', misc.clean_markup(group_total_desc), '', '', '',
                                                             str(amount), '',misc.MEAS_COLOR_NORMAL, str([p1,None]),
                                                             False,False,False,False,False,False,False])
            elif item['itemtype'] == data.schedule.ScheduleItemModel.ANA_SUM:
                iter_res_item = self.store.append(None,[C2('∑'),
                                                        misc.clean_markup(item['description']), '', '', '',
                                                        str(result), '', misc.MEAS_COLOR_NORMAL, str([p1]),
                                                        False,True,False,False,False,False,False])
            elif item['itemtype'] == data.schedule.ScheduleItemModel.ANA_WEIGHT:
                iter_res_item = self.store.append(None,[C1('*'),
                                                        misc.clean_markup(item['description']), '',
                                                        C1(str(item['value'])), '',
                                                        str(result), '', misc.MEAS_COLOR_NORMAL, str([p1]),
                                                        False,True,False,False,True,False,False])
            elif item['itemtype'] == data.schedule.ScheduleItemModel.ANA_TIMES:
                iter_res_item = self.store.append(None,[C1('×∑'),
                                                        misc.clean_markup(item['description']), '',
                                                        C1(str(item['value'])), '',
                                                        str(result), '', misc.MEAS_COLOR_NORMAL, str([p1]),
                                                        False,True,False,False,True,False,False])
            elif item['itemtype'] == data.schedule.ScheduleItemModel.ANA_ROUND:
                description_ = '<b>' + misc.clean_markup(item['description']) + '</b>'
                result_ = '<b>' + misc.clean_markup(str(result)) + '</b>'
                iter_res_item = self.store.append(None,[C2('≈'), description_, '',
                                                        C2(str(item['value'])),
                                                        '', result_, '', misc.MEAS_COLOR_HIGHLIGHTED, str([p1]),
                                                        False,True,False,False,True,False,False])

        self.tree.expand_all()

        # Set selection to the nearest item that was selected

        if old_row != None:
            if old_row > len(self.store):
                old_row = len(self.store)
            path = Gtk.TreePath.new_from_indices([old_row])
            self.tree.set_cursor(path)

    def on_import_clicked(self, filename):
        """Imports analysis from spreadsheet file into analysis view"""

        columntypes = [str, str, str, float, float, float]
        captions = ['Code.', 'Description', 'Unit', 'Rate', 'Qty', 'Amount']
        widths = [80, 200, 80, 80, 80, 80]
        expandables = [False, True, False, False, False, False]

        spreadsheet_dialog = misc.SpreadsheetDialog(self.parent, filename, columntypes, captions, [widths, expandables])
        models = spreadsheet_dialog.run()

        model_copy = copy.deepcopy(self.model)
        # Fill in analysis of rates from models
        data.schedule.parse_analysis(models, model_copy, 0)

        # Modify model
        self.modify_model(model_copy, 'Import from excel sheet')

        log.info('AnalysisView - on_import_clicked - data added')
        self.update_store()

    def exit(self):
        """Get modified model"""

        # Reset undo stack of parent
        undo.setstack(self.stack_old)

        # Set flags
        if self.custom_items:
            self.res_needs_refresh = True

        # Set analysis remarks in model
        if self.entry_analysis_remarks:
            self.model.ana_remarks = self.entry_analysis_remarks.get_text()

        log.info('AnalysisView - exit')
        return (self.model, self.res_needs_refresh)

    def init(self, model, load_default_items=True):
        """Set new model"""
        self.model = copy.deepcopy(model)

        # Setup blank analysis
        if (not self.model.ana_items) and (load_default_items is True):
            self.model.ana_items = self.program_settings['ana_default_add_items']

        # Save undo stack of parent
        self.stack_old = undo.stack()
        # Initialise undo/redo stack
        self.stack = undo.Stack()
        undo.setstack(self.stack)

        # Clear analysis remarks
        if self.entry_analysis_remarks:
            self.entry_analysis_remarks.set_text('')

        # Clear custom items
        self.custom_items.clear()

        # Clear flags
        self.res_needs_refresh = False

        # Update GUI elements according to data
        self.update_store()
        log.info('AnalysisView - init - ' + str(model.code))

    def __init__(self, parent, tree, remarks_entry, database, program_settings, instance_code_callback=None):
        """Initialise AnalysisView class

            Arguments:
                parent: Parent widget (Main window)
                database: Schedule database model
                remarks_entry: Remark entry
                tree: Treeview to implment model
        """
        log.info('AnalysisView - initialise')

        # Setup basic data
        self.parent = parent
        self.database = database
        self.tree = tree
        self.entry_analysis_remarks = remarks_entry
        self.program_settings = program_settings
        self.instance_code_callback = instance_code_callback

        # Track custom items added into view
        self.custom_items = []

        # Setup treeview store

        # Code, Item Description, Unit, Qty, Rate, Amount, Remarks, Colour, Path, [Editables...]
        self.store = Gtk.TreeStore(*([str]*9 + [bool]*7))
        # Treeview columns
        self.column_code = Gtk.TreeViewColumn('Code')
        self.column_code.props.fixed_width = 100
        self.column_code.set_resizable(True)

        self.column_desc = Gtk.TreeViewColumn('Item Description')
        self.column_desc.props.expand = True
        self.column_desc.props.fixed_width = 200
        self.column_desc.set_resizable(True)

        self.column_remarks = Gtk.TreeViewColumn('Remarks')
        self.column_remarks.props.fixed_width = 200
        self.column_remarks.set_resizable(True)

        self.column_unit = Gtk.TreeViewColumn('Unit')
        self.column_unit.props.fixed_width = 80
        self.column_unit.set_resizable(True)

        self.column_qty = Gtk.TreeViewColumn('Qty')
        self.column_qty.props.fixed_width = 80
        self.column_qty.set_resizable(True)

        self.column_rate = Gtk.TreeViewColumn('Rate')
        self.column_rate.props.fixed_width = 80
        self.column_rate.set_resizable(True)

        self.column_amount = Gtk.TreeViewColumn('Amount')
        self.column_amount.props.fixed_width = 100
        self.column_amount.set_resizable(True)

        # Pack Columns
        self.tree.append_column(self.column_code)
        self.tree.append_column(self.column_desc)
        self.tree.append_column(self.column_remarks)
        self.tree.append_column(self.column_unit)
        self.tree.append_column(self.column_qty)
        self.tree.append_column(self.column_rate)
        self.tree.append_column(self.column_amount)
        # Treeview renderers
        self.renderer_code = CellRendererTextView()
        self.renderer_desc = CellRendererTextView()
        self.renderer_remarks = CellRendererTextView()
        self.renderer_unit = CellRendererTextView()
        self.renderer_qty = Gtk.CellRendererText()
        self.renderer_rate = CellRendererTextView()
        self.renderer_amount = CellRendererTextView()
        # Pack renderers
        self.column_code.pack_start(self.renderer_code, True)
        self.column_desc.pack_start(self.renderer_desc, True)
        self.column_remarks.pack_start(self.renderer_remarks, True)
        self.column_unit.pack_start(self.renderer_unit, True)
        self.column_qty.pack_start(self.renderer_qty, True)
        self.column_rate.pack_start(self.renderer_rate, True)
        self.column_amount.pack_start(self.renderer_amount, True)
        # Add attributes
        # Set markup
        self.column_code.add_attribute(self.renderer_code, "markup", 0)
        self.column_desc.add_attribute(self.renderer_desc, "markup", 1)
        self.column_remarks.add_attribute(self.renderer_remarks, "markup", 6)
        self.column_unit.add_attribute(self.renderer_unit, "markup", 2)
        self.column_qty.add_attribute(self.renderer_qty, "markup", 3)
        self.column_rate.add_attribute(self.renderer_rate, "markup", 4)
        self.column_amount.add_attribute(self.renderer_amount, "markup", 5)
        # Set Background
        self.column_code.add_attribute(self.renderer_code, "background", 7)
        self.column_desc.add_attribute(self.renderer_desc, "background", 7)
        self.column_remarks.add_attribute(self.renderer_remarks, "background", 7)
        self.column_unit.add_attribute(self.renderer_unit, "background", 7)
        self.column_qty.add_attribute(self.renderer_qty, "background", 7)
        self.column_rate.add_attribute(self.renderer_rate, "background", 7)
        self.column_amount.add_attribute(self.renderer_amount, "background", 7)
        # Set editables
        self.column_code.add_attribute(self.renderer_code, "editable", 9)
        self.column_desc.add_attribute(self.renderer_desc, "editable", 10)
        self.column_remarks.add_attribute(self.renderer_remarks, "editable", 11)
        self.column_unit.add_attribute(self.renderer_unit, "editable", 12)
        self.column_qty.add_attribute(self.renderer_qty, "editable", 13)
        self.column_rate.add_attribute(self.renderer_rate, "editable", 14)
        self.column_amount.add_attribute(self.renderer_amount, "editable", 15)

        # Add other properties
        self.renderer_code.props.wrap_width = 100
        self.renderer_desc.props.wrap_width = 300
        self.renderer_desc.props.wrap_mode = Pango.WrapMode.WORD_CHAR
        self.renderer_remarks.props.wrap_width = 200
        self.renderer_remarks.props.wrap_mode = Pango.WrapMode.WORD_CHAR
        self.renderer_remarks.props.style = Pango.Style.ITALIC
        self.renderer_code.props.xalign = 1
        self.renderer_qty.props.xalign = 1
        self.renderer_rate.props.xalign = 1
        self.renderer_amount.props.xalign = 0.8

        # Connect callbacks
        self.tree.connect("key_press_event", self.on_key_press_treeview, self.tree)
        self.renderer_code.connect("edited", self.cell_renderer, 0)
        self.renderer_code.connect("editing_started", self.cell_editing_started, 0)
        self.renderer_desc.connect("edited", self.cell_renderer, 1)
        self.renderer_desc.connect("editing_started", self.cell_editing_started, 1)
        self.renderer_remarks.connect("edited", self.cell_renderer, 2)
        self.renderer_remarks.connect("editing_started", self.cell_editing_started, 2)
        self.renderer_qty.connect("edited", self.cell_renderer, 4)
        self.renderer_amount.connect("edited", self.cell_renderer, 6)
        self.renderer_amount.connect("editing_started", self.cell_editing_started, 6)
        self.column_desc.connect("notify", self.on_wrap_column_resized, self.renderer_desc)
        self.column_remarks.connect("notify", self.on_wrap_column_resized, self.renderer_remarks)

        # Set model for store
        self.tree.set_model(self.store)

        # Intialise clipboard
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
