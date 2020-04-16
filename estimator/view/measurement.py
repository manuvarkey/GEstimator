#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  measuremets.py
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

from gi.repository import Gtk, Gdk, GLib

# local files import
from .. import misc, data, undo
from ..undo import undoable
from .scheduledialog import ScheduleDialog

# Get logger object
log = logging.getLogger()


class MeasurementsView:
    """Implements a view for display and manipulation of measurement items over a treeview"""
            
    # Callback functions
    
    def onKeyPressTreeview(self, treeview, event):
        """Handle keypress event"""
        # Unselect all
        if event.keyval == Gdk.KEY_Escape:
            self.tree.get_selection().unselect_all()
            
    def onButtonPressTreeview(self, treeview, event):
        """Handle button press event"""
        # Handle double clicks
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.edit_selected_row()
            
    # Public Methods
        
    def add_heading(self):
        """Add a Heading to measurement view"""
        heading_name = misc.get_user_input_text(self.parent, "Please input Heading. Any additional lines will be printed under the heading.", "Add new Item: Heading", None, True)
        if heading_name != None:
            # get selection
            selection = self.tree.get_selection()
            heading = data.measurement.MeasurementItemHeading([heading_name])
            if selection.count_selected_rows() != 0: # if selection exists
                [model, paths] = selection.get_selected_rows()
                path = paths[0].get_indices()
                self.sch_database.add_measurement_item_at_node(heading, path)
            else: # if no selection append at end
                self.sch_database.add_measurement_item_at_node(heading, None)
            self.update_store()
        else:
            # Return status code for main application interface
            return (misc.WARNING,"Item not added")
                    
    def add_custom(self, oldval=None, itemtype=None, path=None):
        """Add a Custom item to measurement view"""
        item = data.measurement.MeasurementItemCustom(None, itemtype)
        template = [item.itemnos_mask, item.captions, item.columntypes, item.cust_funcs, item.dimensions]
        dialog = ScheduleDialog(self.parent, self.sch_database, *template)
        if oldval is not None: # if edit mode add data
            # Obtain ScheduleDialog model from MeasurementItemCustom model
            old_value_mod = oldval.get_model()
            schmod = old_value_mod[1][0:4]
            dialog.set_model(schmod)
            retdata = dialog.run()
            if retdata is not None: # if edited
                # Obtain MeasurementItemCustom model from ScheduleDialog model
                item.set_model(['MeasurementItemCustom', retdata + old_value_mod[1][4:6]])
                self.sch_database.edit_measurement_item(path, item, oldval) 
            else: # if cancel pressed
                return (misc.INFO,'Cancelled by user. Item not added')
        else: # if normal mode
            retdata = dialog.run()
            if retdata is not None:
                # Obtain custom item from returned data
                custmod = retdata + item.get_model()[1][0:4]
                item.set_model(['MeasurementItemCustom', retdata + item.get_model()[1][4:6]])
                # Get selection
                selection = self.tree.get_selection()
                if selection.count_selected_rows() != 0: # if selection exists
                    [model, paths] = selection.get_selected_rows()
                    path = paths[0].get_indices()
                    self.sch_database.add_measurement_item_at_node(item, path)
                else: # if no selection append at top
                    self.sch_database.add_measurement_item_at_node(item, None)
            else: # if cancel pressed
                return (misc.INFO,'Cancelled by user. Item not added')
        self.update_store()
        
    def delete_selected_row(self):
        """Delete selected rows"""
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            rows = []
            for pathiter in paths:
                rows.append(pathiter.get_indices()[0])
            rows.sort()
            rows.reverse()
            for row in rows:
                self.sch_database.delete_row_meas([row])
                self.update_store()

    def copy_selection(self):
        """Copy selected row to clipboard"""
        items = []
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0: # if selection exists
            test_string = "MeasurementsView"
            [model, paths] = selection.get_selected_rows()
            for pathiter in paths:
                path = pathiter.get_indices()
                if len(path) == 1:
                    item = self.measurements[path[0]]
                    itemmod = item.get_model()
                    items.append(itemmod)
            text = codecs.encode(pickle.dumps([test_string, items]), "base64").decode() # dump item as text
            self.clipboard.set_text(text,-1) # push to clipboard
            log.info("MeasurementsView - copy_selection - Selected item copied to clipboard")
        else: # if no selection
            log.warning("MeasurementsView - copy_selection - No items selected to copy")

    def paste_at_selection(self):
        """Paste copied item at selected row"""
        text = self.clipboard.wait_for_text() # get text from clipboard
        if text != None:
            test_string = "MeasurementsView"
            try:
                itemlist = pickle.loads(codecs.decode(text.encode(), "base64"))  # recover item from string
                if itemlist[0] == test_string:
                    # Get selection
                    selection = self.tree.get_selection()
                    if selection.count_selected_rows() != 0: # if selection exists
                        [model, paths] = selection.get_selected_rows()
                        path = paths[0].get_indices()
                    else:
                        path = None
                        itemlist[1].reverse()
                    # Add items one by one
                    for model in itemlist[1]:
                        if model[0] == 'MeasurementItemCustom':
                            item = data.measurement.MeasurementItemCustom(model[1], model[1][5])
                            self.sch_database.add_measurement_item_at_node(item, path)
                            if path:
                                path = [path[0]+1]
                        elif model[0] == 'MeasurementItemHeading':
                            item = data.measurement.MeasurementItemHeading(model[1])
                            self.sch_database.add_measurement_item_at_node(item, path)
                            if path:
                                path = [path[0]+1]
                        else:
                            pass
                    self.update_store()
            except:
                log.warning('MeasurementsView - paste_at_selection - No valid data in clipboard')
        else:
            log.warning('MeasurementsView - paste_at_selection - No text on the clipboard')
            
    def edit_selected_row(self):
        """Edit selected Row"""
        # Get selection
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            path = paths[0].get_indices()
            item = self.measurements[path[0]]
            if isinstance(item, data.measurement.MeasurementItemHeading):
                oldval = copy.deepcopy(item)
                text = misc.get_user_input_text(self.parent, "Please input Heading. Any additional lines will be printed under the heading.", "Edit Heading", oldval.get_remark(), True)
                if text is not None:
                    newval = data.measurement.MeasurementItemHeading([text])
                    self.sch_database.edit_measurement_item(path, newval, oldval)
            elif isinstance(item, data.measurement.MeasurementItemCustom):
                oldval = copy.deepcopy(item)
                newval = self.add_custom(oldval, item.itemtype, path)
                if newval is not None:
                    self.sch_database.edit_measurement_item(path, newval, oldval)
            # Update GUI
            self.update_store()

    def edit_selected_properties(self):
        """Edit user data of selected item"""
        # Get Selection
        selection = self.tree.get_selection()
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            path = paths[0].get_indices()
            if len(path) == 1:
                item = self.measurements[path[0]]
                if isinstance(item, data.measurement.MeasurementItemCustom):
                    if item.captions_udata:
                        oldmodel = item.get_model()
                        olddata = oldmodel[1][4]
                        # Setup user data dialog
                        newdata = olddata[:]
                        project_settings_dialog = misc.UserEntryDialog(self.parent, 
                                                    'Edit User Data',
                                                    newdata,
                                                    item.captions_udata)
                        # Show user data dialog
                        code = project_settings_dialog.run()
                        # Edit data on success
                        if code:
                            newmodel = copy.deepcopy(oldmodel)
                            newmodel[1][4] = newdata
                            newitem = data.measurement.MeasurementItemCustom(newmodel[1], newmodel[1][5])
                            self.sch_database.edit_measurement_item(path, newitem, item)
                            self.update_store()
                        return None
        return (misc.WARNING,'User data not supported')
        
    def update_store(self):
        """Update GUI of MeasurementsView from data model while trying to preserve selection"""
        log.info('MeasurementsView - update_store')
        
        # Get measurement model
        self.measurements = self.sch_database.get_measurement()
                                
        # Get selection
        selection = self.tree.get_selection()
        old_path = []
        if selection.count_selected_rows() != 0: # if selection exists
            [model, paths] = selection.get_selected_rows()
            old_path = paths[0].get_indices()

        # Update ListView
        self.store.clear()
        for slno, mitem in enumerate(self.measurements.items):
            self.store.append([str(slno+1), mitem.get_text(), mitem.get_tooltip()])

        # Set selection to the nearest item that was selected
        path = [0]
        if old_path != []:
            if old_path[0] < len(self.measurements.items):
                path = old_path[:]
            else:
                path = [len(self.measurements.items)-1]
        self.tree.set_cursor(Gtk.TreePath.new_from_indices(path))
                    
    def __init__(self, parent, sch_database, tree):
        """Initialise MeasurementsView class
        
            Arguments:
                parent: Parent widget (Main window)
                data: Main data model
                tree: Treeview for implementing MeasurementsView
        """
        log.info('MeasurementsView - initialise')
        
        self.parent = parent
        self.tree = tree
        self.sch_database = sch_database
        self.measurements = None
        
        ## Setup treeview store
        # Sl.No., Item Description, Tooltip
        self.store = Gtk.ListStore(str,str,str)
        # Treeview columns
        self.column_slno = Gtk.TreeViewColumn('Sl.No.')
        self.column_desc = Gtk.TreeViewColumn('Item Description')
        self.column_desc.props.expand = True
        # Pack Columns
        self.tree.append_column(self.column_slno)
        self.tree.append_column(self.column_desc)
        # Treeview renderers
        self.renderer_slno = Gtk.CellRendererText()
        self.renderer_desc = Gtk.CellRendererText()
        # Pack renderers
        self.column_slno.pack_start(self.renderer_slno, True)
        self.column_desc.pack_start(self.renderer_desc, True)
        # Add attributes
        self.column_slno.add_attribute(self.renderer_slno, "markup", 0)
        self.column_desc.add_attribute(self.renderer_desc, "markup", 1)
        self.tree.set_tooltip_column(2)
        # Set model for store
        self.tree.set_model(self.store)
        # Set selection mode to multiple
        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        # Intialise clipboard
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        # Connect Callbacks
        self.tree.connect("key-press-event", self.onKeyPressTreeview)
        self.tree.connect("button-press-event", self.onButtonPressTreeview)
        
        # Update GUI elements according to data
        self.update_store()
        
