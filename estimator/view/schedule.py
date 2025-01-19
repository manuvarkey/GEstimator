#!/usr/bin/env python
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

import logging, pickle, codecs
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP
# Rates rounding function
def Currency(x, places=2):
    if int(places) == places:
        return Decimal(x).quantize(Decimal(str(Decimal(10)**(-places))), rounding=ROUND_HALF_UP)
    else:
        precision = int(places)
        base = int((places - int(places))*10)
        mod_x = Decimal(base/(10**precision))*Decimal(x*(10**precision)/base).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
        return Decimal(mod_x).quantize(Decimal(str(Decimal(10)**(-precision))), rounding=ROUND_HALF_UP)

from gi.repository import Gtk, Gdk, GLib, Pango

# local files import
from .. import misc, data
from . import analysis
from .cellrenderercustomtext import CellRendererTextView

# Setup logger object
log = logging.getLogger(__name__)

class ScheduleView:
    """Implement Schedule view"""

    def __init__(self, parent, database, box, compact=False, show_sum=False, read_only=False, instance_code_callback=None):
        """Setup schedule view and connect signals

            Arguments:
                parent: Parent window
                database: database of items to be displayed
                box: Box to implement schedule view
        """
        log.info('ScheduleView - Initialise')

        # Passed data
        self.parent = parent
        self.database = database
        self.box = box
        self.show_sum = show_sum
        self.read_only = read_only
        self.instance_code_callback = instance_code_callback

        # Additional data
        captions = ['Code', 'Description', 'Unit', 'Rate', 'Qty',
                    'Amount', 'Remarks']
        expands = [False, True, False, False, False, False, False]
        if compact:
            widths = [150, 300, 80, 80, 80, 80, 80]
        else:
            widths = [150, 400, 80, 80, 80, 100, 150]
        columntypes = [str, str, str, float, float, None, str]

        # Setup treestore and filter
        # Additional bool array for editable
        # str for background colour, full description and emphasis
        self.store = Gtk.TreeStore(*([str]*7 + [bool] + [int] + [bool]*5 + [str]*2 + [int]))
        self.filter = self.store.filter_new()
        self.filter.set_visible_func(self.filter_func, data=[0,15,2,6])

        self.search_field = Gtk.SearchEntry()
        self.search_field.set_width_chars(30)
        self.search_bar = Gtk.SearchBar()
        self.search_bar.set_show_close_button(True)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.tree = Gtk.TreeView(self.filter)
        # Pack widgets
        self.search_bar.add(self.search_field)
        self.box.pack_start(self.search_bar, False, False, 0)
        self.box.pack_start(scrolled, True, True, 0)
        scrolled.add(self.tree)


        # Setup tree view
        self.tree.set_grid_lines(3)
        self.tree.set_enable_tree_lines(True)
        self.tree.set_search_equal_func(self.equal_func, [0,15,2,6])
        self.tree.set_show_expanders(False)
        self.tree.set_level_indentation(30)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.tree.set_rubber_banding(True)
        self.tree.props.activate_on_single_click = False
        self.tree.connect("button-press-event", self.on_click_event)
        self.tree.connect("key-press-event", self.on_key_press_treeview, self.tree)
        self.search_field.connect("search-changed", self.on_search)

        self.columns = dict()
        self.cells = dict()
        for slno, [caption, expand, width, columntype] in enumerate(zip(captions, expands, widths, columntypes)):
            column = Gtk.TreeViewColumn(caption)

            if columntype is str:
                cell = CellRendererTextView()
                cell.connect("edited", self.on_cell_edited_text, slno)
                cell.connect("editing_started", self.on_cell_edit_started, slno)
            elif columntype is float:
                cell = Gtk.CellRendererText()
                cell.connect("edited", self.on_cell_edited_num, slno)

            self.tree.append_column(column)
            self.columns[caption] = column
            self.cells[caption] = cell
            column.pack_start(cell, True)
            column.set_expand(expand)
            column.add_attribute(cell, "text", slno)

            if caption == 'Description' and not self.read_only:
                column.add_attribute(cell, "full_text", 15)
                column.add_attribute(cell, "editable", 7+slno)
            else:
                column.add_attribute(cell, "editable", 7+slno)

            if caption == 'Description':
                column.connect("notify", self.on_wrap_column_resized, cell)

            column.set_resizable(True)
            column.add_attribute(cell, "cell_background", 14)
            column.add_attribute(cell, "weight", 16)
            column.set_fixed_width(width)

        if compact:
            self.cells['Remarks'].props.wrap_width = 80
            self.cells['Description'].props.wrap_width = 300
        else:
            self.cells['Remarks'].props.wrap_width = 150
            self.cells['Description'].props.wrap_width = 400

        self.cells['Description'].props.wrap_mode = Pango.WrapMode.WORD_CHAR
        self.cells['Remarks'].props.wrap_mode = Pango.WrapMode.WORD_CHAR
        self.cells['Rate'].props.xalign = 1
        self.cells['Qty'].props.xalign = 1
        self.cells['Amount'].props.xalign = 1

        # Intialise clipboard
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.update_store()

    def update_store(self, mark=False, select_path=None):
        """
            Updates store to match database
            If mark=True checks rate with analysed rate and set row background
        """
        log.info('ScheduleView - update_store')

        # Get selection
        selection = self.tree.get_selection()
        old_item = None
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            old_item = paths[-1].get_indices()

        # Clear store
        self.store.clear()

        # Metrics to be returned on mark
        with_mismatch = 0
        delta1 = 0
        delta2 = 0
        delta3 = 0
        without_analysis = 0
        item_count = 0

        # Fill in data in treeview
        sum_total = 0
        sch_table = self.database.get_item_table()
        for category, items in sch_table.items():
            data = ['', category, '', '', '', '', '']
            if self.read_only:
                bools = [False] + [False] + [False]*5
            else:
                bools = [False] + [True] + [False]*5
            category_row = data + bools + [misc.MEAS_COLOR_NORMAL, category, 700]
            category_iter = self.store.append(None, category_row)
            for code, item_list in items.items():
                # Add items to store
                item = item_list[0]
                item_desc = misc.get_ellipsized_text(item[1], misc.MAX_DESC_LEN)
                item_unit = item[2]
                item_rate = str(item[3]) if item[3] != 0 else ''
                item_qty = str(item[4]) if item[4] != 0 else ''
                item_amount = str(Currency(item[3]*item[4])) if item[3]*item[4] != 0 else ''
                item_remarks = item[5]
                item_colour = item[6]

                sum_total = sum_total + Currency(item[3]*item[4])

                data = [code, item_desc, item_unit, item_rate,
                        item_qty, item_amount, item_remarks]
                if self.read_only:
                    bools = [False] + [False] + [False]*5
                else:
                    bools = [True] + [True] + [True]*3 + [False,True]

                if item_colour:
                    colour = item_colour
                else:
                    colour = misc.MEAS_COLOR_NORMAL
                full_description = item[1]

                # If mark, check rates with analysed rate
                if mark and item_unit !='':
                    sch_item = self.database.get_item(code)
                    if sch_item.results:
                        delta = abs(Currency(sch_item.get_ana_rate()) - Currency(item[3]))
                        if delta == 0:
                            colour = misc.MEAS_COLOR_NORMAL
                        elif delta <= 0.1:
                            colour = misc.MEAS_COLOR_LOCKED
                            with_mismatch = with_mismatch + 1
                            delta1 = delta1 + 1
                        elif delta <= 1:
                            colour = misc.MEAS_COLOR_LOCKED_L1
                            with_mismatch = with_mismatch + 1
                            delta2 = delta2 + 1
                        else:
                            colour = misc.MEAS_COLOR_LOCKED_L2
                            with_mismatch = with_mismatch + 1
                            delta3 = delta3 + 1
                    else:
                        colour = misc.MEAS_COLOR_MISSING
                        without_analysis = without_analysis + 1

                    item_count = item_count + 1

                item_row = data + bools + [colour, full_description, 400]
                item_iter = self.store.append(category_iter, item_row)

                for sub_item in item_list[1]:
                    code = sub_item[0]
                    desc = misc.get_ellipsized_text(sub_item[1], misc.MAX_DESC_LEN)
                    unit = sub_item[2]
                    rate = str(sub_item[3]) if sub_item[3] != 0 else ''
                    qty = str(sub_item[4]) if sub_item[4] != 0 else ''
                    amount = str(Currency(sub_item[3]*sub_item[4])) if sub_item[3]*sub_item[4] != 0 else ''
                    remarks = sub_item[5]
                    sub_item_colour = sub_item[6]

                    sum_total = sum_total + Currency(sub_item[3]*sub_item[4])

                    data = [code, desc, unit, rate, qty, amount, remarks]
                    if self.read_only:
                        bools = [False] + [False] + [False]*5
                    else:
                        bools = [True] + [True] + [True]*3 + [False,True]

                    if sub_item_colour:
                        colour = sub_item_colour
                    else:
                        colour = misc.MEAS_COLOR_NORMAL

                    full_description = sub_item[1]

                    # If mark, check rates with analysed rate
                    if mark and unit !='':
                        sch_item = self.database.get_item(code)
                        if sch_item.results:
                            delta = abs(Currency(sch_item.get_ana_rate()) - Currency(sub_item[3]))
                            if delta == 0:
                                colour = misc.MEAS_COLOR_NORMAL
                            elif delta <= 0.1:
                                colour = misc.MEAS_COLOR_LOCKED
                                with_mismatch = with_mismatch + 1
                                delta1 = delta1 + 1
                            elif delta <= 1:
                                colour = misc.MEAS_COLOR_LOCKED_L1
                                with_mismatch = with_mismatch + 1
                                delta2 = delta2 + 1
                            else:
                                colour = misc.MEAS_COLOR_LOCKED_L2
                                with_mismatch = with_mismatch + 1
                                delta3 = delta3 + 1
                        else:
                            colour = misc.MEAS_COLOR_MISSING
                            without_analysis = without_analysis + 1
                        item_count = item_count + 1

                    row = data + bools + [colour, full_description, 400]
                    self.store.append(item_iter, row)

        # Append sum row
        if self.show_sum:
            data = ['', 'SUM TOTAL', '', '', '', str(sum_total), '']
            bools = [False]*7
            colour = misc.MEAS_COLOR_HIGHLIGHTED
            row = data + bools + [colour, '', 700]
            self.store.append(None, row)

        # Expand all expanders
        self.tree.expand_all()

        # Set selection to the nearest item that was selected
        if select_path is None:
            select_item = old_item
        else:
            select_item = select_path

        if select_item is not None:
            if len(select_item) > 0:
                if len(self.store) == 0:
                    return
                elif select_item[0] >= len(self.store):
                    select_item = [len(self.store)-1]
                elif len(select_item) > 1:
                    path = Gtk.TreePath.new_from_indices(select_item[0:1])
                    try:
                        store_row = self.store.get_iter(path)
                        store_row_len = self.store.iter_n_children(store_row)
                        if store_row_len == 0:
                            select_item = [select_item[0]]
                        elif select_item[1] >= store_row_len:
                            select_item = [select_item[0], store_row_len-1]
                        elif len(select_item) == 3:
                            path = Gtk.TreePath.new_from_indices(select_item[0:2])
                            try:
                                store_row_2 = self.store.get_iter(path)
                                store_row_2_len = self.store.iter_n_children(store_row_2)
                                if store_row_2_len == 0:
                                    select_item = [select_item[0],select_item[1]]
                                elif select_item[2] >= store_row_2_len:
                                    select_item[2] = store_row_2_len-1
                            except ValueError:
                                select_item = [select_item[0]]
                    except ValueError:
                        return
            path = Gtk.TreePath.new_from_indices(select_item)
            self.tree.set_cursor(path)

        # Return metrics
        if mark:
            return [item_count, with_mismatch, delta1, delta2, delta3, without_analysis]

    def update_sum(self):
        """Update sum of amounts"""
        sum_total = [0]

        def sumfunc(model, path, iter, sum_total):
            row = model[iter]
            if row[3] != '' and row[4] != '':
                sum_total[0] = sum_total[0] + float(row[5])
            elif row[0] == '' and row[1] == 'SUM TOTAL':
                model[iter][5] = str(Currency(sum_total[0]))
                return True

        self.store.foreach(sumfunc, sum_total)

    def insert_row_from_database(self, path, code):

        if len(path) == 1:

            if path[0] == len(self.store):
                position = len(self.store) - 1
            else:
                position = path[0]

            data = ['', code, '', '', '', '', '']
            bools = [False] + [True] + [False]*5
            category_row = data + bools + [misc.MEAS_COLOR_NORMAL, code, 700]

            self.store.insert(None, position, category_row)

        elif len(path) in (2,3):

            item = self.database.get_item(code, copy_ana=False)
            item_desc = misc.get_ellipsized_text(item.description, misc.MAX_DESC_LEN)
            item_unit = item.unit
            item_rate = str(item.rate) if item.rate != 0 else ''
            item_qty = str(item.qty) if item.qty != 0 else ''
            item_amount = str(Currency(item.rate*item.qty)) if item.rate*item.qty != 0 else ''
            item_remarks = item.remarks

            data = [code, item_desc, item_unit, item_rate,
                    item_qty, item_amount, item_remarks]
            bools = [True] + [True] + [True]*3 + [False,True]
            item_row = data + bools + [misc.MEAS_COLOR_NORMAL, item.description, 400]

            if len(path) == 2:
                parent_iter = self.store.get_iter(Gtk.TreePath.new_from_indices([path[0]]))
                position = path[1]
            else:
                parent_iter = self.store.get_iter(Gtk.TreePath.new_from_indices([path[0], path[1]]))
                position = path[2]
            self.store.insert(parent_iter, position, item_row)
            self.tree.expand_all()

    def insert_rows_from_database(self, item_dict):
        for path, code in sorted(item_dict.items()):
            self.insert_row_from_database(path, code)
        self.update_sum()

    def delete_rows_from_database(self, paths):
        for path in sorted(paths, reverse=True):
            item_iter = self.store.get_iter(Gtk.TreePath.new_from_indices(path))
            self.store.remove(item_iter)
        self.update_sum()

    def get_selected_paths(self):
        path_indices = []
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0:  # if selection exists
            [tree, paths] = selection.get_selected_rows()
            for path in paths:
                path_index = path.get_indices()
                path_indices.append(path_index)
        return path_indices

    def get_next_path(self, iter_path, reverse=False):
        if iter_path is None:
            return None

        iter_row = self.store.get_iter(iter_path)

        if not reverse:
            if self.store.iter_has_child(iter_row):
                return self.store.get_path(self.store.iter_nth_child(iter_row,0))
            elif self.store.iter_next(iter_row):
                return self.store.get_path(self.store.iter_next(iter_row))
            else:
                parent = self.store.iter_parent(iter_row)
                if parent:
                    if self.store.iter_next(parent):
                        if self.store.iter_next(parent):
                            return self.store.get_path(self.store.iter_next(parent))
                        else:
                            great_parent = self.store.iter_parent(parent)
                            if self.store.iter_next(great_parent):
                                return self.store.get_path(self.store.iter_next(great_parent))
        else:
            if self.store.iter_previous(iter_row):
                prev_row = self.store.iter_previous(iter_row)
                if self.store.iter_has_child(prev_row):
                    n_last_child = self.store.iter_n_children(prev_row) - 1
                    child = self.store.iter_nth_child(prev_row, n_last_child)
                    if self.store.iter_has_child(child):
                        n_last_grand_child = self.store.iter_n_children(child) - 1
                        grand_child = self.store.iter_nth_child(child, n_last_grand_child)
                        return self.store.get_path(grand_child)
                    else:
                        return self.store.get_path(child)
                else:
                    return self.store.get_path(self.store.iter_previous(iter_row))
            elif self.store.iter_parent(iter_row):
                return self.store.get_path(self.store.iter_parent(iter_row))

        return None

    def get_selected(self, include_category=True):
        codes = OrderedDict()

        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0:  # if selection exists
            [tree, paths] = selection.get_selected_rows()
            for path in paths:
                path_index = tuple(path.get_indices())
                if len(path) == 1 and include_category and path[0] < len(self.store)-1:
                    category = self.filter[path][1]
                    codes[path_index] = category
                elif len(path) in [2,3]:
                    code = self.filter[path][0]
                    codes[path_index] = code

        return codes

    def get_selected_codes(self, get_key=False):
        selected = self.get_selected(include_category=False)
        codes = []
        for path, code in selected.items():
            codes.append(code)
        if get_key:
            key = self.database.get_item_key(codes[0])
            return (codes[0], key)
        else:
            return codes

    def set_selection(self, code=None, path=None):

        if code:
            def search_func(model, path, iterator, data):
                code = data[0]
                if model[iterator][0] == code:
                    data[1] = path
                    return True

            data = [code, None]
            self.store.foreach(search_func, data)
            if data[1] is not None:
                self.tree.set_cursor(data[1])
                self.tree.scroll_to_cell(data[1], None)
        elif path:
            path_iter = Gtk.TreePath.new_from_indices(path)
            self.tree.set_cursor(path_iter)
            self.tree.scroll_to_cell(path_iter, None)

    def add_category_at_selection(self, newcat):
        """Add category at selection"""

        paths = self.get_selected_paths()
        if paths:
            path = paths[-1]
        else:
            path = None
        order = self.database.insert_schedule_category(newcat, path=path)

        if order is not False:
            # Add new item to store
            self.insert_row_from_database([order], newcat)
            self.set_selection(path=[order])

    def add_item_at_selection(self, items, local_res_code=None):
        """Add items at selection"""

        selected = self.get_selected()

        # Setup position to insert
        if selected:
            last_selected = list(selected.items())[-1]
            path = last_selected[0]
        else:
            path = None

        [items_added, net_ress_added] = self.database.insert_item_multiple(items, path=path, number_with_path=True, local_res_code=local_res_code)

        if items_added:
            # Add new items to store
            self.insert_rows_from_database(items_added)

            # Set selection
            selection_path = list(items_added.items())[-1][0]
            self.set_selection(path=selection_path)

            if net_ress_added:
                return (True, True)
            else:
                return (True, False)
        else:
            return None

    def add_sub_ana_items(self, items):
        """Add items under sub-analysis"""
        [items_added, net_ress_added] = self.database.insert_item_multiple(items, path=None, number_with_path=False)
        if items_added:
            # Add new items to store
            self.insert_rows_from_database(items_added)

            if net_ress_added:
                return (True, True)
            else:
                return (True, False)
        else:
            return None

    def delete_selected_items(self):
        selected = self.get_selected()
        self.database.delete_schedule(selected)

        # Update store
        self.delete_rows_from_database(selected.keys())

    def update_selected_rates(self):
        codes = self.get_selected_codes()
        if codes:
            if self.database.update_rates(codes):
                self.update_store()
                return True
            else:
                return False

        elif codes is None:
            return None

    def update_selected_qty(self, rounding):
        codes = self.get_selected_codes()
        if codes:
            if self.database.update_qty(codes, rounding):
                self.update_store()
                return True
            else:
                return False
        elif codes is None:
            return None

    def update_colour(self, colour):
        codes = self.get_selected_codes()
        if codes:
            if self.database.update_item_colour(codes, colour):
                selected = self.get_selected(include_category=False)
                for path, code in selected.items():
                    iterator = self.store.get_iter(Gtk.TreePath.new_from_indices(path))
                    self.store[iterator][14] = colour
                return True
            else:
                return False

    def cell_renderer_text(self, path, column, oldvalue, newvalue):
        """Undoable function for modifying value of a treeview cell"""
        iterator = self.store.get_iter(Gtk.TreePath.new_from_indices(path))

        # Update category
        if len(path) == 1 and column == 1:

            if not self.database.update_schedule_category(oldvalue, newvalue):
                log.warning('ScheduleView - cell_renderer_text - category not updated - ' + str(oldvalue) + ':' + str(newvalue))
            else:
                self.store[iterator][column] = newvalue
                if column == 1:  # For custom cellrenderercustomtext
                    self.store[iterator][15] = newvalue
                self.evaluate_amount(iterator)

        # Update items
        elif len(path) in [2,3]:
            code = self.store[iterator][0]
            if not self.database.update_item_schedule(code, newvalue, column):
                log.warning('ScheduleView - cell_renderer_text - value not updated - ' + str(oldvalue) + ':' + str(newvalue) + ' {' + str(column) + '}')
            else:
                if column == 1:
                    self.store[iterator][column] = misc.get_ellipsized_text(newvalue, misc.MAX_DESC_LEN)
                    self.store[iterator][15] = newvalue
                else:
                    self.store[iterator][column] = newvalue
                self.evaluate_amount(iterator)
            self.update_sum()

    def copy_selection(self):
        """Copy selected row to clipboard"""
        selected = self.get_selected()

        if selected: # if selection exists
            test_string = "ScheduleView"

            items = []
            for path in selected:
                if len(path) in [2,3]:
                    code = selected[path]
                    item = self.database.get_item(code, modify_res_code=False)
                    if item:
                        items.append(item)
            if items:
                text = codecs.encode(pickle.dumps([test_string, self.instance_code_callback(), items]), "base64").decode() # dump item as text
                self.clipboard.set_text(text,-1) # push to clipboard
                log.info('ScheduleView - copy_selection - Item copied to clipboard - ' + str(path))
                return
        # if no selection
        log.warning("ScheduleView - copy_selection - No items selected to copy")

    def paste_at_selection(self):
        """Paste copied item at selected row"""

        text = self.clipboard.wait_for_text() # get text from clipboard
        if text != None:
            test_string = "ScheduleView"
            try:
                itemlist = pickle.loads(codecs.decode(text.encode(), "base64"))  # recover item from string
                if itemlist[0] == test_string:
                    check_instance_code = itemlist[1]
                    items = itemlist[2]
                    if check_instance_code == self.instance_code_callback():
                        self.add_item_at_selection(items)
                    else:
                        self.add_item_at_selection(items, local_res_code=check_instance_code)
            except:
                selected = self.get_selected()
                (treepath, focus_column) = self.tree.get_cursor()
                # Paste whole content if multiple selection
                if len(selected) > 1 and focus_column:
                    focus_col_num = self.tree.get_columns().index(focus_column)
                    if focus_col_num in (3,4):
                        with self.database.group('Paste into schedule column ' + str(focus_col_num)):
                            for path in selected:
                                self.on_cell_edited_num(None, ':'.join(map(str,path)), text, focus_col_num)
                    elif focus_col_num in (1,2,6):
                        text = text.strip('\n')
                        with self.database.group('Paste into schedule column ' + str(focus_col_num)):
                            for path in selected:
                                self.on_cell_edited_text(None, ':'.join(map(str,path)), text, focus_col_num)
                # Matrix paste across rows and columns if single selection
                elif len(selected) == 1 and focus_column:
                    focus_col_num = self.tree.get_columns().index(focus_column)
                    path = treepath
                    text_list = text.strip('\n').split('\n')
                    with self.database.group('Paste into schedule column ' + str(focus_col_num)):
                        for text_line in text_list:
                            text_line_list = text_line.strip('\t').split('\t')
                            for count, text_element in enumerate(text_line_list):
                                if focus_col_num + count in (3,4):
                                    self.on_cell_edited_num(None, ':'.join(map(str,path.get_indices())), text_element, focus_col_num + count)
                                elif focus_col_num + count in (1,2,6):
                                    text = text.strip('\n')
                                    self.on_cell_edited_text(None, ':'.join(map(str,path.get_indices())), text_element, focus_col_num + count)
                            path = self.get_next_path(path)
                            if path is None:
                                break
        else:
            log.warning('ScheduleView - paste_at_selection - No text in clipboard')

    def evaluate_amount(self, iterator):
        rate = self.store[iterator][3]
        qty = self.store[iterator][4]
        unit = self.store[iterator][2]
        amount = ''
        try:
            amount = str(Currency(float(rate)*float(qty)))
        except ValueError:
            log.warning("ScheduleView - evaluate_amount - evaluation of amount failed")
        self.store[iterator][5] = amount

    def start_search(self):
        self.search_bar.set_search_mode(True)

    # Search functions

    def equal_func(self, model, column, key, iterator, cols):
        """Equal function for interactive search"""
        search_string = ''
        for col in cols:
            search_string += ' ' + model[iterator][col].lower()
        for word in key.split():
            if word.lower() not in search_string:
                return True
        return False

    def filter_func(self, model, model_iter, cols):
        """Searches in treestore"""

        def check_key(key, model_iter):
            if key is None or key == "":
                return True
            else:
                search_string = ''
                for col in cols:
                    if model[model_iter][col] is not None:
                        search_string += ' ' + model[model_iter][col].lower()
                for word in key.split():
                    if word.lower() not in search_string:
                        return False
                return True

        def search_children(key, model_iter):
            cur_iter = model.iter_children(model_iter)
            while cur_iter:
                if check_key(key, cur_iter) == True:
                    return True
                else:
                    code = search_children(key, cur_iter)
                    if code == True:
                        return True
                cur_iter = model.iter_next(cur_iter)
            return False

        key = self.search_field.get_text()
        # Check item
        if check_key(key, model_iter) == True:
            return True
        # Check children
        else:
            return search_children(key, model_iter)


    # Callbacks

    def on_search(self, entry):
        # Refilter model
        self.filter.refilter()
        # Expand all expanders
        self.tree.expand_all()

    def on_click_event(self, button, event):
        """Select item on double click"""
        # Grab focus
        self.tree.grab_focus()
        # Handle double clicks
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.select_action()

    def on_key_press_treeview(self, widget, event, treeview):
        """Handle keypress event"""
        keyname = event.get_keyval()[1]
        state = event.get_state()
        shift_pressed = bool(state & Gdk.ModifierType.SHIFT_MASK)
        control_pressed = bool(state & Gdk.ModifierType.CONTROL_MASK)

        # Key Board events
        if keyname in [Gdk.KEY_Escape]:  # Unselect all
            self.tree.get_selection().unselect_all()
            return

        if keyname in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:  # Select element
            if control_pressed:
                self.select_action_alt()
            else:
                self.select_action()
            return

        if self.read_only and keyname == Gdk.KEY_f and control_pressed:  # Search keycode
            self.search_bar.set_search_mode(True)
            return

        if not self.read_only and control_pressed:
            if keyname in (Gdk.KEY_c, Gdk.KEY_C):
                self.copy_selection()
            elif keyname in (Gdk.KEY_v, Gdk.KEY_V):
                self.paste_at_selection()
            return

        # Handle tabs
        path, col = treeview.get_cursor()
        if path != None:
            columns = [c for c in treeview.get_columns()]
            colnum = columns.index(col)
            store = treeview.get_model()

            row_path = path.copy()

            if col in columns:
                if keyname in [Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab]:
                    def select_func(tree, path, col, edit, activate):
                        tree.grab_focus()
                        tree.set_cursor(path, col, edit)
                        if activate:
                            tree.row_activated(path, col)
                        return False

                    if shift_pressed == 1:
                        # Search over editable states
                        while row_path:
                            # Determine starting column
                            # For same row
                            if row_path == path:
                                end = (colnum-1)+7
                            # For different row
                            else:
                                end = 13
                            for col in range(end,6,-1):
                                if self.store[row_path][col] == True:
                                    prev_column = columns[col-7]
                                    edit = True
                                    activate = False
                                    treeview.scroll_to_cell(row_path, prev_column, False)
                                    if row_path == path:
                                        GLib.idle_add(select_func, treeview, row_path, prev_column, edit, activate)
                                    else:
                                        GLib.timeout_add(200, select_func, treeview, row_path, prev_column, edit, activate)
                                    return
                            row_path = self.get_next_path(row_path, reverse=True)
                    else:
                        # Search over editable states
                        while row_path:
                            # Determine starting column
                            # For same row
                            if row_path == path:
                                start = (colnum+1)+7
                            # For different row
                            else:
                                start = 7
                            for col in range(start, 14):
                                if self.store[row_path][col] == True:
                                    next_column = columns[col-7]
                                    edit = True
                                    activate = False
                                    treeview.scroll_to_cell(row_path, next_column, False)
                                    if row_path == path:
                                        GLib.idle_add(select_func, treeview, row_path, next_column, edit, activate)
                                    else:
                                        GLib.timeout_add(200, select_func, treeview, row_path, next_column, edit, activate)
                                    return
                            row_path = self.get_next_path(row_path, reverse=False)

    def select_action(self):
        pass

    def select_action_alt(self):
        pass

    def on_cell_edited_text(self, widget, path_str, new_text, column):
        """Treeview cell renderer for editable text field

            User Data:
                column: column in ListStore being edited
        """
        path = [int(part) for part in path_str.split(':')]
        iterator = self.store.get_iter_from_string(path_str)
        oldvalue = self.store[iterator][column]

        # Call undoable function only if there is a change in value
        if new_text != oldvalue:
            self.cell_renderer_text(path, column, oldvalue, new_text)

    def on_cell_edited_num(self, widget, path_str, new_text, column):
        """Treeview cell renderer for editable number field

            User Data:
                column: column in ListStore being edited
        """
        path = [int(part) for part in path_str.split(':')]
        iterator = self.store.get_iter_from_string(path_str)
        oldvalue = self.store[iterator][column]

        try:  # check whether item evaluates fine
            if column == 3:
                evaluated_no = float(Currency(eval(new_text)))
            else:
                evaluated_no = round(eval(new_text), 4)

            if evaluated_no == 0:
                evaluated = ''
            else:
                evaluated = str(evaluated_no)
        except:
            log.warning("ScheduleView - on_cell_edited_num - evaluation of ["
            + new_text + "] failed")
            return

        # Call undoable function only if there is a change in value
        if evaluated != oldvalue:
            self.cell_renderer_text(path, column, oldvalue, evaluated)

    def on_cell_edit_started(self, widget, editable, path, column):
        """Fill in text from schedule when schedule view column get edited

            User Data:
                column: column in ListStore being edited
        """
        editable.editor.connect("key-press-event", self.on_key_press_treeview, self.tree)

    def on_wrap_column_resized(self, column, pspec, cell):
        """ Automatically adjust wrapwidth to column width"""

        width = column.get_width()
        oldwidth = cell.props.wrap_width

        if width > 0 and width != oldwidth:
            cell.props.wrap_width = width
            # Force redraw of treeview
            GLib.idle_add(column.queue_resize)


class SelectScheduleDialog:
    """Shows a dialog to select a schedule item """

    def __init__(self, parent, database, settings, simple=False):
        """Setup dialog window and connect signals

            Arguments:
                parent: Parent window
                database: database of items to be displayed
        """
        log.info('SelectScheduleDialog - Initialise')

        # Passed data
        self.database = database
        self.settings = settings
        self.simple = simple

        # Setup dialog
        title = 'Select the schedule item to be added'

        if self.simple:
            self.dialog_window = Gtk.Dialog(title, parent, Gtk.DialogFlags.MODAL,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                 Gtk.STOCK_OK, Gtk.ResponseType.OK))
        else:
            self.dialog_window = Gtk.Dialog(title, parent, Gtk.DialogFlags.MODAL,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                 Gtk.STOCK_ADD, Gtk.ResponseType.APPLY,
                 'Modify & Add', Gtk.ResponseType.OK))

        self.dialog_window.set_transient_for(parent)
        self.dialog_window.set_default_response(Gtk.ResponseType.OK)
        self.dialog_window.set_resizable(True)
        self.dialog_window.set_size_request(-1,600)

        dialogBox = self.dialog_window.get_content_area()
        dialogBox.set_border_width(6)
        self.action_area = self.dialog_window.get_action_area()
        self.action_area.props.margin_top = 12

        if self.simple:
            box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
            self.scheduleview = ScheduleView(self.dialog_window,
                                            self.database,
                                            box,
                                            compact=False,
                                            read_only=True)
            # Overide functions of default resource view
            self.scheduleview.select_action = self.select_action
            dialogBox.pack_start(box, True, True, 0)
            # Set selection mode to single
            self.scheduleview.tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
            # Grab focus
            self.scheduleview.tree.grab_focus()
        else:
            # Combobox for libraries
            self.library_combo = Gtk.ComboBoxText()
            self.libraries = self.database.get_library_names()
            for library in self.libraries:
                if library:
                    self.library_combo.append_text(str(library))
            if self.library_combo:
                self.library_combo.set_active(0)

            # Pack widgets
            box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
            self.stack = Gtk.Stack()
            self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            dialogBox.pack_start(box, True, True, 0)
            box.pack_start(self.library_combo, False, False, 0)
            box.pack_start(self.stack, True, True, 0)


            self.scheduleviews = dict()
            for library in self.libraries:
                box_res = Gtk.Box.new(Gtk.Orientation.VERTICAL,0)
                self.stack.add_named(box_res, library)
                with self.database.using_library(library):
                    sch_view = ScheduleView(self.dialog_window,
                                            self.database,
                                            box_res,
                                            compact = False,
                                            read_only = True)
                    self.scheduleviews[library] = sch_view
                    # Overide functions of schedule view
                    sch_view.select_action = self.select_action
                    sch_view.select_action_alt = self.select_action_alt
            if self.scheduleviews:
                self.scheduleview = self.scheduleviews[self.libraries[0]]
                self.scheduleview.tree.grab_focus()

            # Connect signals
            self.library_combo.connect("changed", self.on_combo_changed)

    def on_combo_changed(self, combo):
        name = combo.get_active_text()
        self.scheduleview = self.scheduleviews[name]
        self.stack.set_visible_child_name(name)
        self.scheduleview.tree.grab_focus()

    def run(self):
        """Show dialog and return with schedule

            Returns:
            Returns Schedule items or None if user does not select any item.
        """
        # Show Dialog window
        self.dialog_window.show_all()
        response = self.dialog_window.run()

        # Evaluate response

        # Simple select
        if self.simple:
            if response == Gtk.ResponseType.OK:
                self.dialog_window.hide()
                return self.scheduleview.get_selected_codes(get_key=True)
        # Standard select
        else:
            name = self.library_combo.get_active_text()  # Get current library name
            selected_codes = self.scheduleview.get_selected_codes()
            selected_items = []

            # Modify and add
            if response == Gtk.ResponseType.OK:
                if selected_codes:
                    # Get settings
                    delete_rows = int(eval(self.settings['ana_copy_delete_rows']))
                    ana_rows = self.settings['ana_copy_add_items']
                    sch_mult_text = self.settings['sch_rate_mult_factor']
                    try:
                        sch_mult = Currency(eval(sch_mult_text), 5)
                    except:
                        sch_mult = 1

                    for selected_code in selected_codes:
                        # Get item from selected library
                        with self.database.using_library(name):
                            item = self.database.get_item(selected_code)
                            proj_code = self.database.get_project_settings()['project_item_code']

                        if item:
                            # Modify current item according to settings
                            item.rate = item.rate * sch_mult
                            if delete_rows and ana_rows and len(item.ana_items) > delete_rows:
                                item.ana_items = item.ana_items[:-delete_rows] + ana_rows

                            # Modify item reference
                            remarks = proj_code + ' ' + item.code
                            item.remarks = remarks
                            # TODO add option to add MF remark
                            # if sch_mult != 1:
                            #     item.remarks = "{0}\nMF = {1} ({2})".format(remarks, sch_mult, sch_mult_text)
                            # else:
                            #     item.remarks = remarks

                            log.info('SelectScheduleDialog - run - Selected with modification - ' + selected_code)
                            selected_items.append(item)

                    if selected_items:
                        # Hide and Return
                        codes = [item.code for item in selected_items]
                        with self.database.using_library(name):
                            sub_ana_items = self.database.get_sub_ana_items(codes, modify_res_code=True)
                        self.dialog_window.hide()
                        return selected_items, sub_ana_items

            # Add without modiying
            elif response == Gtk.ResponseType.APPLY:
                if selected_codes:
                    for selected_code in selected_codes:
                        # Get item from selected library
                        with self.database.using_library(name):
                            item = self.database.get_item(selected_code)
                            proj_code = self.database.get_project_settings()['project_item_code']
                        if item:
                            # Modify item reference
                            remarks = proj_code + ' ' + item.code
                            item.remarks = remarks

                            log.info('SelectScheduleDialog - run - Selected without modification - ' + selected_code)
                            selected_items.append(item)

                    if selected_items:
                        # Hide and Return
                        codes = [item.code for item in selected_items]
                        with self.database.using_library(name):
                            sub_ana_items = self.database.get_sub_ana_items(codes, modify_res_code=True)
                        self.dialog_window.hide()
                        return selected_items, sub_ana_items

        # Cancel
        # Hide and Return
        self.dialog_window.hide()
        log.info('SelectScheduleDialog - run - Cancelled')
        return []

    def select_action(self):
        self.dialog_window.response(Gtk.ResponseType.OK)

    def select_action_alt(self):
        self.dialog_window.response(Gtk.ResponseType.APPLY)

    def on_key_press_treeview(self, treeview, event):
        """Handle keypress event"""
        keyname = event.get_keyval()[1]
