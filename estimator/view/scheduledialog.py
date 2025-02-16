#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# scheduledialog.py
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

import copy, logging, codecs, pickle, textwrap
from gi.repository import Gtk, Gdk, GLib, Pango

# local files import
from .. import misc, data, undo
from . import schedule
from .cellrenderercustomtext import CellRendererTextView
from .schedule import SelectScheduleDialog
from ..undo import undoable

# Get logger object
log = logging.getLogger()

class ScheduleViewGeneric:
    """Implements a view for display and manipulation of ScheduleGeneric over a treeview"""

    # Call backs for treeview

    def onScheduleCellEditedText(self, widget, row, new_text, column):
        """Treeview cell renderer for editable text field

            User Data:
                column: column in ListStore being edited
        """
        self.cell_renderer_text(int(row), column, new_text)

    def onScheduleCellEditedNum(self, widget, row, new_text, column):
        """Treeview cell renderer for editable number field

            User Data:
                column: column in ListStore being edited
        """
        try:  # check whether item evaluates fine
            if new_text != '':
                eval(new_text)
        except:
            log.warning("ScheduleViewGeneric - onScheduleCellEditedNum - evaluation of ["
            + new_text + "] failed")
            return
        self.cell_renderer_text(int(row), column, new_text)

    def onEditStarted(self, widget, editable, path, column):
        """Fill in text from schedule when schedule view column get edited

            User Data:
                column: column in ListStore being edited
        """
        row = int(path)
        item = self.schedule.get_item_by_index(row).get_model()
        editable.set_text(str(item[column]))
        editable.editor.connect("key-press-event", self.onKeyPressTreeviewSchedule, self.tree)

    # for browsing with tab key
    def onKeyPressTreeviewSchedule(self, widget, event, treeview):
        """Handle key presses"""

        def select_func(tree, treepath, col):
            tree.grab_focus()
            tree.set_cursor(treepath, col, True)
            return False

        keyname = event.get_keyval()[1]
        state = event.get_state()
        shift_pressed = bool(state & Gdk.ModifierType.SHIFT_MASK)
        path, col = treeview.get_cursor()
        if path != None:
            ## only visible columns!!
            columns = [c for c in treeview.get_columns() if c.get_visible() and self.celldict[c].props.editable]
            rows = [r for r in treeview.get_model()]
            if col in columns:
                colnum = columns.index(col)
                rownum = path[0]
                if keyname in [Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab]:
                    if shift_pressed == 1:
                        if colnum - 1 >= 0:
                            prev_column = columns[colnum - 1]
                        else:
                            tmodel = treeview.get_model()
                            titer = tmodel.iter_previous(tmodel.get_iter(path))
                            if titer is None:
                                prev_column = columns[0]
                            else:
                                path = tmodel.get_path(titer)
                                prev_column = columns[-1]
                            treeview.scroll_to_cell(path, prev_column, False)
                        GLib.idle_add(select_func, treeview, path, prev_column)
                        return
                    else:
                        if colnum + 1 < len(columns):
                            next_column = columns[colnum + 1]
                        else:
                            tmodel = treeview.get_model()
                            titer = tmodel.iter_next(tmodel.get_iter(path))
                            if titer is None:
                                next_column = columns[colnum]
                            else:
                                path = tmodel.get_path(titer)
                                next_column = columns[0]
                            treeview.scroll_to_cell(path, next_column, False)
                        GLib.idle_add(select_func, treeview, path, next_column)
                        return

                elif keyname in [Gdk.KEY_Alt_L , Gdk.KEY_Alt_R , Gdk.KEY_Escape]:  # unselect all
                    self.tree.get_selection().unselect_all()

    def on_wrap_column_resized(self, column, pspec, cell):
        """ Automatically adjust wrapwidth to column width"""

        width = column.get_width()
        oldwidth = cell.props.wrap_width

        if width > 0 and width != oldwidth:
            cell.props.wrap_width = width
            # Force redraw of treeview
            GLib.idle_add(column.queue_resize)

    # Class methods

    def setup_column_props(self, widths, expandables):
        """Set column properties
            Arguments:
                widths: List of column widths type-> [int, ...]. None values are skiped.
                expandables: List of expand property type-> [bool, ...]. None values are skiped.
        """
        for column, width, expandable in zip(self.columns, widths, expandables):
            if width != None:
                column.set_min_width(width)
                column.set_fixed_width(width)
                self.celldict[column].props.wrap_width = width
            if expandable != None:
                column.set_expand(expandable)

    def set_selection(self, path=None):
        if path:
            path_iter = Gtk.TreePath.new_from_indices(path)
            self.tree.set_cursor(path_iter)
            self.tree.scroll_to_cell(path_iter, None)

    def insert_item_at_selection(self, itemlist):
        """Insert items at selected row"""
        if itemlist:
            selection = self.tree.get_selection()
            if selection.count_selected_rows() != 0:  # if selection exists
                [model, paths] = selection.get_selected_rows()
                rows = []
                for i in range(0, len(itemlist)):
                    rows.append(paths[0].get_indices()[0]+i+1)
                self.insert_item_at_row(itemlist, rows)
                self.set_selection([paths[0].get_indices()[0]+i+1])
            else:  # if no selection
                rows = []
                for i in range(0, len(itemlist)):
                    rows.append(i)
                self.insert_item_at_row(itemlist, rows)
                self.set_selection([i])

    def delete_selected_rows(self):
        """Delete selected rows"""
        selection = self.tree.get_selection()
        [model, paths] = selection.get_selected_rows()
        rows = []
        for path in paths:  # get rows
            rows.append(int(path.get_indices()[0]))

        # delete rows
        self.delete_row(rows)

    @undoable
    def append_item(self, itemlist):
        """Undoable function to append items to schedule"""
        newrows = []

        for item in itemlist:
            self.schedule.append_item(item)
            newrows.append(self.schedule.length() - 1)
        self.update_store()

        yield "Append data items to schedule at row '{}'".format(newrows)
        # Undo action
        self.delete_row(newrows)

    @undoable
    def insert_item_at_row(self, itemlist, rows):
        """Undoable function to insert items to schedule at given rows

            Remarks:
                Need rows to be sorted.
        """
        newrows = []
        for i in range(0, len(rows)):
            self.schedule.insert_item_at_index(rows[i], itemlist[i])
            newrows.append(rows[i])
        self.update_store()

        yield "Insert data items to schedule at rows '{}'".format(rows)
        # Undo action
        self.delete_row(newrows)

    @undoable
    def delete_row(self, rows):
        """Undoable function to delete a set of rows"""
        newrows = []
        items = []

        rows.sort()
        for i in range(0, len(rows)):
            items.append(self.schedule[rows[i] - i])
            newrows.append(rows[i])
            self.schedule.remove_item_at_index(rows[i] - i)
        self.update_store()

        yield "Delete data items from schedule at rows '{}'".format(rows)
        # Undo action
        self.insert_item_at_row(items, newrows)

    @undoable
    def cell_renderer_text(self, row, column, newvalue):
        """Undoable function for modifying value of a treeview cell"""
        oldvalue = self.schedule[row][column]
        self.schedule[row][column] = newvalue
        self.update_store()

        yield "Change data item at row:'{}' and column:'{}'".format(row, column)
        # Undo action
        self.schedule[row][column] = oldvalue
        self.update_store()

    def copy_selection(self):
        """Copy selected rows to clipboard"""
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0:  # if selection exists
            test_string = "Schedule:" + str(self.columntypes)
            [model, paths] = selection.get_selected_rows()
            items = []
            for path in paths:
                row = int(path.get_indices()[0])  # get item row
                item = self.schedule[row]
                items.append(item)  # save items
            text = codecs.encode(pickle.dumps([test_string, items]), "base64").decode() # dump item as text
            self.clipboard.set_text(text, -1)  # push to clipboard
        else:  # if no selection
            log.warning("ScheduleViewGeneric - copy_selection - No items selected to copy")

    def paste_at_selection(self):
        """Paste copied item at selected row"""
        text = self.clipboard.wait_for_text()  # get text from clipboard
        if text is not None:
            test_string = "Schedule:" + str(self.columntypes)
            try:
                itemlist = pickle.loads(codecs.decode(text.encode(), "base64"))  # recover item from string
                if itemlist[0] == test_string:
                    self.insert_item_at_selection(itemlist[1])
            except:
                log.warning('ScheduleViewGeneric - paste_at_selection - No valid data in clipboard')
        else:
            log.warning("ScheduleViewGeneric - paste_at_selection - No text in clipboard.")

    def model_width(self):
        """Returns the width of model"""
        return len(self.columntypes)

    def get_model(self):
        """Return data model"""
        return self.schedule.get_model()

    def set_model(self, schedule):
        """Set data model"""
        self.schedule.set_model(schedule)
        self.update_store()

    def set_caption(self, caption, slno):
        """Update column captions"""
        if slno < len(self.captions):
            self.captions[slno] = caption
            self.columns[slno].set_title(caption)

    def clear(self):
        """Clear all schedule items"""
        self.schedule.clear()
        self.update_store()

    def update_store(self):
        """Update store to reflect modified schedule"""
        log.info('ScheduleViewGeneric - update_store')
        # Add or remove required rows
        rownum = 0
        for row in self.store:
            rownum += 1
        rownum = len(self.store)
        if rownum > self.schedule.length():
            for i in range(rownum - self.schedule.length()):
                del self.store[-1]
        else:
            for i in range(self.schedule.length() - rownum):
                self.store.append()

        # Find formated items and fill in values
        for row in range(0, self.schedule.length()):
            item = self.schedule.get_item_by_index(row).get_model()
            display_item = []
            for item_elem, columntype, render_func in zip(item, self.columntypes, self.render_funcs):
                try:
                    if item_elem != "" or columntype == misc.MEAS_CUST:
                        if columntype == misc.MEAS_CUST:
                            display_item.append(render_func(item, row))
                        if columntype == misc.MEAS_DESC:
                            display_item.append(item_elem)
                        elif columntype == misc.MEAS_NO:
                            value = str(int(eval(item_elem)))
                            display_item.append(value)
                        elif columntype == misc.MEAS_L:
                            value = str(round(float(eval(item_elem)), 3))
                            display_item.append(value)
                    else:
                        display_item.append("")
                except TypeError:
                    display_item.append("")
                    log.warning('ScheduleViewGeneric - Wrong value loaded in store - '  + str(item_elem))
            self.store[row] = display_item

    def __init__(self, parent, tree, captions, columntypes, render_funcs):
        """Initialise ScheduleViewGeneric class

            Arguments:
                parent: Parent widget (dialog/window)
                tree: Treeview for implementing schedule
                captions: Captions to be displayed in columns
                columntypes: Column data type
                    (takes the values misc.MEAS_NO,
                                      misc.MEAS_L,
                                      misc.MEAS_DESC,
                                      misc.MEAS_CUST)
                render_funcs: Fucntions generating values of CUSTOM columns
        """
        log.info('ScheduleViewGeneric - Initialise')
        # Setup variables
        self.parent = parent
        self.tree = tree
        self.captions = copy.copy(captions)
        self.columntypes = columntypes
        self.render_funcs = render_funcs
        self.schedule = data.schedule_meas.ScheduleGeneric()

        # Setup treeview
        data_types = [str] * len(self.columntypes)
        self.store = Gtk.ListStore(*data_types)
        self.tree.set_model(self.store)
        self.celldict = dict()
        self.columns = []

        # Interactive search function
        def equal_func(model, column, key, iter, cols):
            """Equal function for interactive search"""
            search_string = ''
            for col in cols:
                search_string += ' ' + model[iter][col].lower()
            for word in key.split():
                if word.lower() not in search_string:
                    return True
            return False

        # Set interactive search function
        cols = [i for i,x in enumerate(self.columntypes) if x == misc.MEAS_DESC]
        self.tree.set_search_equal_func(equal_func, [0,1,5])

        for columntype, caption, render_func, i in zip(self.columntypes, self.captions, self.render_funcs,
                                                       range(len(self.columntypes))):
            cell = CellRendererTextView()

            column = Gtk.TreeViewColumn(caption, cell, text=i)
            column.props.resizable = True

            self.columns.append(column)  # Add column to list of columns
            self.celldict[column] = cell  # Add cell to column map for future ref

            self.tree.append_column(column)
            self.tree.props.search_column = 0

            if columntype == misc.MEAS_NO:
                cell.set_property("editable", True)
                column.props.min_width = 75
                column.props.fixed_width = 75
                if render_func is None:
                    cell.connect("edited", self.onScheduleCellEditedNum, i)
                    cell.connect("editing_started", self.onEditStarted, i)
                else:
                    cell.connect("edited", render_func, i)
            elif columntype == misc.MEAS_L:
                cell.set_property("editable", True)
                column.props.min_width = 75
                column.props.fixed_width = 75
                if render_func is None:
                    cell.connect("edited", self.onScheduleCellEditedNum, i)
                    cell.connect("editing_started", self.onEditStarted, i)
                else:
                    cell.connect("edited", render_func, i)
            elif columntype == misc.MEAS_DESC:
                cell.set_property("editable", True)
                column.props.sizing = Gtk.TreeViewColumnSizing.AUTOSIZE
                column.props.resizable = False
                column.props.fixed_width = 150
                column.props.min_width = 150
                column.props.expand = True
                cell.props.wrap_width = 150
                cell.props.wrap_mode = Pango.WrapMode.WORD_CHAR
                column.connect("notify", self.on_wrap_column_resized, cell)
                if render_func is None:
                    cell.connect("edited", self.onScheduleCellEditedText, i)
                    cell.connect("editing_started", self.onEditStarted, i)
                else:
                    cell.connect("edited", render_func, i)
            elif columntype == misc.MEAS_CUST:
                cell.set_property("editable", False)
                column.props.sizing = Gtk.TreeViewColumnSizing.AUTOSIZE
                column.props.resizable = False
                column.props.fixed_width = 100
                column.props.min_width = 100
                cell.props.wrap_width = 100
                cell.props.wrap_mode = Pango.WrapMode.WORD_CHAR
                column.connect("notify", self.on_wrap_column_resized, cell)
                if render_func is None:
                    cell.connect("edited", self.onScheduleCellEditedText, i)
                    cell.connect("editing_started", self.onEditStarted, i)
                else:
                    cell.connect("edited", render_func, i)

        # Intialise clipboard
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)  # initialise clipboard

        # Connect signals with custom userdata
        self.tree.connect("key-press-event", self.onKeyPressTreeviewSchedule, self.tree)


class ScheduleDialog:
    """Class implements a dialog box for entry of measurement records"""

    # General Methods

    def model_width(self):
        """Width of schedule model loaded"""
        return self.schedule_view.model_width()

    def get_model(self):
        """Get data model"""
        remark = self.remark_cell.get_text()
        item_remarks = [cell.get_text() for cell in self.item_remarks_cell]
        data = [self.itemnosid, self.schedule_view.get_model(), remark, item_remarks]
        return data

    def set_item_button(self, itemno, button):
        if itemno:
            item = self.sch_database.get_item(itemno, modify_res_code=False)
            full_description = item.description
            if item.parent is not None:
                parent = self.sch_database.get_item(item.parent)
                full_description = parent.description + '\n' + full_description
            item_desc = misc.get_ellipsized_text(full_description, misc.MAX_DESC_LEN_MEAS, singleline=True)
            display_text = misc.get_tabular_text([[itemno, item_desc]])
            button.set_label(str(display_text))
            button.get_child().set_xalign(0)
            button.set_has_tooltip(True)
            button.set_tooltip_text(full_description)
        else:
            button.set_label('-')

    def set_model(self, data):
        """Set data model"""
        self.itemnosid = copy.copy(data[0])
        # Set item buttons
        for itemnoid, button in zip(self.itemnosid, self.item_buttons):
            itemno = self.sch_database.get_item_code(itemnoid)
            self.set_item_button(itemno, button)
            self.itemnos.append(itemno)
        # Set schedule
        self.schedule_view.clear()
        self.schedule_view.set_model(copy.deepcopy(data[1]))
        self.schedule_view.update_store()
        # Set remark cells
        self.remark_cell.set_text(data[2])
        for cell, text in zip(self.item_remarks_cell, data[3]):
            cell.set_text(text)

    # Callbacks for GUI elements

    def onDeleteWindow(self, *args):
        """Callback called on pressing the close button of main window"""

        log.info('ScheduleDialog - onDeleteWindow called')
        # Ask confirmation from user
        message = 'Any changes made will be lost if you continue.\n Are you sure you want to Cancel ?'
        title = 'Confirm Cancel'
        dialogWindow = Gtk.MessageDialog(self.window,
                                 Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                 Gtk.MessageType.QUESTION,
                                 Gtk.ButtonsType.YES_NO,
                                 message)
        dialogWindow.set_transient_for(self.window)
        dialogWindow.set_title(title)
        dialogWindow.set_default_response(Gtk.ResponseType.NO)
        dialogWindow.show_all()
        response = dialogWindow.run()
        dialogWindow.destroy()
        if response == Gtk.ResponseType.NO:
            # Do not propogate signal
            log.info('ScheduleDialog - onDeleteWindow - Cancelled by user')
            self.window.run()
            return True

    def OnItemSelectClicked(self, button, index):
        """Select item from schedule on selection using combo box"""
        settings = self.sch_database.get_project_settings()
        select_schedule = SelectScheduleDialog(self.window, self.sch_database, settings, simple=True)
        response = select_schedule.run()
        if response:
            self.itemnos[index] = response[0]
            self.itemnosid[index] = response[1]
            self.set_item_button(response[0], button)

    def OnRemarkEdited(self, entry, index):
        text = entry.get_text()
        col_index = self.itemnos_mapping[index]
        if col_index is not None:
            base_caption = self.captions[col_index]
            if col_index:
                text_wraped = '\n'.join(textwrap.wrap(text, 10))
                new_text = base_caption + '\n' + text_wraped
                self.schedule_view.set_caption(new_text, col_index)

    def onClearButtonPressed(self, button, button_item, index):
        """Clear combobox selecting schedule item"""
        button_item.set_label('-')
        self.itemnos[index] = None
        self.itemnosid[index] = None

    def onButtonScheduleAddPressed(self, button):
        """Add row to schedule"""
        items = []
        items.append(data.schedule_meas.ScheduleItemGeneric([""] * self.model_width()))
        self.schedule_view.insert_item_at_selection(items)

    def onButtonScheduleAddMultPressed(self, button):
        """Add multiple rows to schedule"""
        user_input = misc.get_user_input_text(self.window, "Please enter the number \nof rows to be inserted",
                                             "Number of Rows")
        try:
            number_of_rows = int(user_input)
        except:
            log.warning("Invalid number of rows specified")
            return
        items = []
        for i in range(0, number_of_rows):
            items.append(data.schedule_meas.ScheduleItemGeneric([""] * self.model_width()))
        self.schedule_view.insert_item_at_selection(items)

    def onButtonScheduleDeletePressed(self, button):
        """Delete item from schedule"""
        self.schedule_view.delete_selected_rows()

    def onUndoSchedule(self, button):
        """Undo changes in schedule"""
        undo.setstack(self.stack)  # select schedule undo stack
        log.info('ScheduleViewGeneric - ' + str(self.stack.undotext()))
        self.stack.undo()

    def onRedoSchedule(self, button):
        """Redo changes in schedule"""
        undo.setstack(self.stack)  # select schedule undo stack
        log.info('ScheduleViewGeneric - ' + str(self.stack.redotext()))
        self.stack.redo()

    def onCopySchedule(self, button):
        """Copy rows from schedule"""
        self.schedule_view.copy_selection()

    def onPasteSchedule(self, button):
        """Paste rows in schedule"""
        self.schedule_view.paste_at_selection()

    def onImportScheduleClicked(self, button):
        """Import xlsx file into schedule"""
        filename = self.builder.get_object("filechooserbutton_schedule").get_filename()

        spread_col_types = []
        for columntype in self.columntypes:
            if columntype == misc.MEAS_NO:
                spread_col_types.append(int)
            elif columntype == misc.MEAS_L:
                spread_col_types.append(float)
            elif columntype == misc.MEAS_DESC:
                spread_col_types.append(str)
            elif columntype == misc.MEAS_CUST:
                spread_col_types.append(None)

        spreadsheet_dialog = misc.SpreadsheetDialog(self.window, filename, spread_col_types, self.captions, self.dimensions, allow_formula=True)
        models = spreadsheet_dialog.run()

        items = []
        for model in models:
            item = data.schedule_meas.ScheduleItemGeneric(model)
            items.append(item)
        self.schedule_view.insert_item_at_selection(items)

    def __init__(self, parent, sch_database, itemnosid, itemnos_mapping, captions, columntypes, render_funcs, dimensions=None):
        """Initialise ScheduleDialog class

            Arguments:
                parent: Parent widget (Main window)
                sch_database: Agreement schedule
                itemnos: Itemsnos of items being meaured
                captions: Captions of columns
                columntypes: Data types of columns.
                             Takes following values:
                                misc.MEAS_NO: Integer
                                misc.MEAS_L: Float
                                misc.MEAS_DESC: String
                                misc.MEAS_CUST: Value provided through render function
                render_funcs: Fucntions generating values of CUSTOM columns
                dimensions: List for two lists passing column widths and expand properties
        """
        log.info('ScheduleDialog - Initialise')
        # Setup variables
        self.parent = parent
        self.itemnosid = itemnosid
        self.itemnos = itemnosid
        self.itemnos_mapping = itemnos_mapping
        self.captions = captions
        self.columntypes = columntypes
        self.render_funcs = render_funcs
        self.sch_database = sch_database
        self.dimensions = dimensions

        # Save undo stack of parent
        self.stack_old = undo.stack()
        # Initialise undo/redo stack
        self.stack = undo.Stack()
        undo.setstack(self.stack)

        # Setup dialog window
        self.builder = Gtk.Builder()
        self.builder.add_from_file(misc.abs_path("interface","scheduledialog.glade"))
        self.window = self.builder.get_object("dialog")
        self.window.set_transient_for(self.parent)
        self.window.set_default_size(1100,600)
        self.builder.connect_signals(self)

        # Get required objects
        self.listbox_itemnos = self.builder.get_object("listbox_itemnos")
        self.tree = self.builder.get_object("treeview_schedule")

        # Setup schdule view for items
        self.schedule_view = ScheduleViewGeneric(self.parent,
            self.tree, self.captions, self.columntypes, self.render_funcs)
        if dimensions is not None:
            self.schedule_view.setup_column_props(*dimensions)

        # Setup remarks row
        self.remark_cell = self.builder.get_object("remarks_entry")
        self.item_buttons = []
        self.item_remarks_cell = []

        for itemno, index in zip(self.itemnos, list(range(len(self.itemnos)))):
            # Get items in row
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            entry = Gtk.Entry()
            button_clear = Gtk.Button(stock=Gtk.STOCK_CLEAR)
            button_item = Gtk.Button.new_with_label("None")

            # Pack row
            row.add(hbox)
            hbox.pack_start(entry, False, True, 3)
            hbox.pack_start(button_item, True, True, 3)
            hbox.pack_start(button_clear, False, True, 0)

            # Set additional properties
            entry.props.width_request = 50
            button_clear.connect("clicked", self.onClearButtonPressed, button_item, index)
            button_item.connect("clicked", self.OnItemSelectClicked, index)
            entry.connect("changed", self.OnRemarkEdited, index)

            # Add to list box
            self.listbox_itemnos.add(row)

            # Save variables
            self.item_buttons.append(button_item)
            self.item_remarks_cell.append(entry)

    def run(self):
        """Display dialog box and return data model

            Returns:
                Data Model on Ok
                None on Cancel
        """
        self.window.show_all()
        response = self.window.run()
        # Reset undo stack of parent
        undo.setstack(self.stack_old)

        if response == 1:
            data = self.get_model()
            self.window.destroy()
            log.info('ScheduleDialog - run - Response Ok')
            return data
        else:
            self.window.destroy()
            log.info('ScheduleDialog - run - Response Cancel')
            return None
