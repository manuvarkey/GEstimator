#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  project.py
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
from . import analysis
from .. import misc, data, undo
from ..undo import undoable

# Setup logger object
log = logging.getLogger(__name__)

class ProjectSettings:
    
    def __init__(self, parent, database):

        builder = Gtk.Builder()
        builder.add_from_file(misc.abs_path("interface", "projectsettings.glade"))
        dialog = builder.get_object("settings_dialog")
        dialog.set_transient_for(parent)
        dialog.set_modal(True)
        builder.connect_signals(self)
        
        # Get objects
        project_name_entry = builder.get_object('project_name_entry')
        project_code_item_entry = builder.get_object('project_item_code_entry')
        project_code_resource_entry = builder.get_object('project_resource_code_entry')
        
        # Get existing project settings
        settings = database.get_project_settings()
        
        try:
            # Set existing values
            project_name_entry.set_text(settings['project_name'])
            project_code_item_entry.set_text(settings['project_item_code'])
            project_code_resource_entry.set_text(settings['project_resource_code'])
        except:
            log.error('ProjectSettings - Existing values could not be read')
        
        # Show settings dialog
        response = dialog.run()
        
        if response == 1:
            # Set settings
            settings['project_name'] = project_name_entry.get_text()
            settings['project_item_code'] = project_code_item_entry.get_text()
            settings['project_resource_code'] = project_code_resource_entry.get_text()
            
            # Save project settings
            database.set_project_settings(settings)
        dialog.destroy()

    def ana_add_sum(self, widget):
        self.analysis_view.add_sum()

    def ana_add_weight(self, widget):
       self.analysis_view.add_weight()

    def ana_add_times(self, widget):
        self.analysis_view.add_times()

    def ana_add_round(self, widget):
        self.analysis_view.add_round()

    def ana_delete_selected_row(self, widget):
        self.analysis_view.delete_selected_row()
        
        
class ProgramSettings:
    
    def __init__(self, parent, database, settings, library_dir):

        builder = Gtk.Builder()
        builder.add_from_file(misc.abs_path("interface", "programsettings.glade"))
        dialog = builder.get_object("settings_dialog")
        dialog.set_transient_for(parent)
        dialog.set_modal(True)
        builder.connect_signals(self)
        
        # Get objects
        ana_delete_spin = builder.get_object('ana_delete_spin')
        location_button = builder.get_object('location_button')
        self.stack_main = builder.get_object('stack_main')
        
        # Setup modify analysis view
        tree_modify = builder.get_object('treeview_modify_settings')
        self.analysis_view_modify = analysis.AnalysisView(dialog, tree_modify, None, database, settings)
        model = data.schedule.ScheduleItemModel('','')
        model.ana_items = settings['ana_copy_add_items']
        self.analysis_view_modify.init(model)
        # Setup modify analysis view
        tree_default = builder.get_object('treeview_default_settings')
        self.analysis_view_default = analysis.AnalysisView(dialog, tree_default, None, database, settings)
        model = data.schedule.ScheduleItemModel('','')
        model.ana_items = settings['ana_default_add_items']
        self.analysis_view_default.init(model)
        
        self.analysis_view = self.analysis_view_modify
        
        # Set existing values
        ana_delete_spin.set_value(int(eval(settings['ana_copy_delete_rows'])))
        location_button.set_label(library_dir)
        
        # Show settings dialog
        response = dialog.run()
        
        # Retreive values
        (model_ret_modify, update_flag) = self.analysis_view_modify.exit()
        (model_ret_default, update_flag) = self.analysis_view_default.exit()
        
        if response == 1:
            # Set settings
            settings['ana_copy_delete_rows'] = str(ana_delete_spin.get_value())
            settings['ana_copy_add_items'] = model_ret_modify.ana_items
            settings['ana_default_add_items'] = model_ret_default.ana_items
        dialog.destroy()
        
    def update_focus_child(self):
        name = self.stack_main.get_visible_child_name()
        if name == 'modify_analysis':
            self.analysis_view = self.analysis_view_modify
        else:
            self.analysis_view = self.analysis_view_default

    def ana_add_res_group(self, widget):
        self.update_focus_child()
        self.analysis_view.add_res_group()

    def ana_add_sum(self, widget):
        self.update_focus_child()
        self.analysis_view.add_sum()

    def ana_add_weight(self, widget):
        self.update_focus_child()
        self.analysis_view.add_weight()

    def ana_add_times(self, widget):
        self.update_focus_child()
        self.analysis_view.add_times()

    def ana_add_round(self, widget):
        self.update_focus_child()
        self.analysis_view.add_round()

    def ana_delete_selected_row(self, widget):
        self.update_focus_child()
        self.analysis_view.delete_selected_row()
        
    def show_database_folder(self, widget):
        filename = widget.get_label()
        misc.open_file(filename)

