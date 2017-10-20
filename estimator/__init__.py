#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# estimator
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

import subprocess, os, ntpath, platform, sys, logging, queue, threading, pickle, copy
import tempfile, shutil, appdirs
from decimal import Decimal
from collections import OrderedDict

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject, Gio, GdkPixbuf

# local files import
from . import undo, misc, data, view
from . undo import undoable, group

# Get logger object
log = logging.getLogger()


class MainWindow:

    # General Methods

    def display_status(self, status_code, message):
        """Displays a formated message in Infobar
            
            Arguments:
                status_code: Specifies the formatting of message.
                             (Takes the values misc.ERROR,
                              misc.WARNING, misc.INFO]
                message: The message to be displayed
        """
        infobar_main = self.builder.get_object("infobar_main")
        label_infobar_main = self.builder.get_object("label_infobar_main")
        infobar_revealer = self.builder.get_object("infobar_revealer")
        
        if status_code == misc.ERROR:
            infobar_main.set_message_type(Gtk.MessageType.ERROR)
            label_infobar_main.set_text(message)
        elif status_code == misc.WARNING:
            infobar_main.set_message_type(Gtk.MessageType.WARNING)
            label_infobar_main.set_text(message)
        elif status_code == misc.INFO:
            infobar_main.set_message_type(Gtk.MessageType.INFO)
            label_infobar_main.set_text(message)
        else:
            log.warning('display_status - Malformed status code')
            return
        log.info('display_status - ' + message)
        infobar_revealer.set_reveal_child(True)
        
    def run_command(self, exec_func, data=None):
        """Return progress object"""
        
        # Show progress page
        self.hidden_stack.set_visible_child_name('Progress')
        
        # Setup progress object
        progress_label = self.builder.get_object("progress_label")
        progress_bar = self.builder.get_object("progress_bar")
        progress = misc.ProgressWindow(parent=None, 
                                       label=progress_label, 
                                       progress=progress_bar)
        
        def callback_combined(progress, data, stack):
            # End progress
            progress.pulse(end=True)
            # Run process
            if data:
                exec_func(progress, data)
            else:
                exec_func(progress)
            # Change page
            def show_default():
                stack.set_visible_child_name('Default')
            
            GLib.timeout_add_seconds(1, show_default)
        
        # Run process in seperate thread
        que = queue.Queue()
        thread = threading.Thread(target=lambda q, arg: q.put(callback_combined(progress, data, self.hidden_stack)), args=(que, 2))
        thread.daemon = True
        thread.start()
    
    def update(self):
        """Refreshes all displays"""
        log.info('MainWindow update called')
        self.resource_view.update_store()
        self.schedule_view.update_store()
            
    # Main Window

    def on_delete_window(self, *args):
        """Callback called on pressing the close button of main window"""
        
        log.info('MainWindow - on_exit called')
        
        # Ask confirmation from user
        if self.stack.haschanged():
            message = 'You have unsaved changes which will be lost if you continue.\n Are you sure you want to exit ?'
            title = 'Confirm Exit'
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
                log.info('MainWindow - on_exit - Cancelled by user')
                return True

        log.info('MainWindow - on_exit - Exiting')
        self.sch_database.close_database()
        return False

    def on_open_project_clicked(self, button=None, filename=None):
        """Open project selected by  the user"""
        
        if filename:
            self.filename = filename
        else:
            # Create a filechooserdialog to open:
            # The arguments are: title of the window, parent_window, action,
            # (buttons, response)
            open_dialog = Gtk.FileChooserDialog("Open project File", self.window,
                                                Gtk.FileChooserAction.OPEN,
                                                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))
            # Remote files can be selected in the file selector
            open_dialog.set_local_only(True)
            # Dialog always on top of the textview window
            open_dialog.set_modal(True)
            # Set filters
            open_dialog.set_filter(self.builder.get_object("Project"))
            # Set window position
            open_dialog.set_gravity(Gdk.Gravity.CENTER)
            open_dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

            response_id = open_dialog.run()
            # If response is "ACCEPT" (the button "Save" has been clicked)
            if response_id == Gtk.ResponseType.ACCEPT:
                # get filename and set project as active
                self.filename = open_dialog.get_filename()
                # Destroy dialog
                open_dialog.destroy()
            # If response is "CANCEL" (the button "Cancel" has been clicked)
            else:
                log.info("MainWindow - on_open_project_clicked - cancelled: FileChooserAction.OPEN")
                # Destroy dialog
                open_dialog.destroy()
                self.builder.get_object('popup_open_project').hide()
                return
            
        try:
            # Close existing database
            self.sch_database.close_database()
            # Copy selected file to temporary location
            shutil.copy(self.filename, self.filename_temp)
            # Opn temp file
            self.sch_database.open_database(self.filename_temp)
            self.project_active = True
            self.update()
            self.display_status(misc.INFO, 'Project opened successfully')
        except:
            log.exception("MainWindow - on_open_project_clicked - Error opening project file - " + self.filename)
            self.display_status(misc.ERROR, "Project could not be opened: Error opening file")
        self.builder.get_object('popup_open_project').hide()
        
    def on_open_project_selected(self, recent):
        uri = recent.get_current_uri()
        filename = misc.uri_to_file(uri)
        self.on_open_project_clicked(None, filename)
        window_title = self.filename + ' - ' + misc.PROGRAM_NAME
        self.window.set_title(window_title)
        self.builder.get_object('popup_open_project').hide()

    def on_save_project_clicked(self, button):
        """Save project to file already opened"""
        if self.project_active is False:
            self.on_saveas_project_clicked(button)
        else:            
            try:
                # Copy current temporary file to filename
                shutil.copy(self.filename_temp, self.filename)
                self.update()
                self.display_status(misc.INFO, "Project successfully saved")
                log.info('MainWindow - on_save_project_clicked -  Project successfully saved')
                # Save point in stack for checking change state
                self.stack.savepoint()
            except:
                log.error("MainWindow - on_save_project_clicked - Error opening file - " + self.filename)
                self.display_status(misc.ERROR, "Project file could not be opened for saving")

    def on_saveas_project_clicked(self, button):
        """Save project to file selected by the user"""
        # Create a filechooserdialog to open:
        # The arguments are: title of the window, parent_window, action,
        # (buttons, response)
        open_dialog = Gtk.FileChooserDialog("Save project as...", self.window,
                                            Gtk.FileChooserAction.SAVE,
                                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                             Gtk.STOCK_SAVE, Gtk.ResponseType.ACCEPT))
        # Remote files can be selected in the file selector
        open_dialog.set_local_only(False)
        # Dialog always on top of the textview window
        open_dialog.set_modal(True)
        # Set filters
        open_dialog.set_filter(self.builder.get_object("Project"))
        # Set window position
        open_dialog.set_gravity(Gdk.Gravity.CENTER)
        open_dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        # Set overwrite confirmation
        open_dialog.set_do_overwrite_confirmation(True)
        # Set default name
        open_dialog.set_current_name("newproject")
        response_id = open_dialog.run()
        # If response is "ACCEPT" (the button "Save" has been clicked)
        if response_id == Gtk.ResponseType.ACCEPT:
            # Get filename and set project as active
            filename = open_dialog.get_filename()
            if misc.PROJECT_EXTENSION not in filename.lower():
                self.filename = misc.posix_path(filename + misc.PROJECT_EXTENSION)
            else:
                self.filename = misc.posix_path(filename)
            self.project_active = True
            log.info('MainWindow - on_saveas_project_clicked -  Project set as active')
            # Call save project
            self.on_save_project_clicked(button)
            # Setup window name
            window_title = self.filename + ' - ' + misc.PROGRAM_NAME
            self.window.set_title(window_title)
            # Save point in stack for checking change state
            self.stack.savepoint()

        # If response is "CANCEL" (the button "Cancel" has been clicked)
        elif response_id == Gtk.ResponseType.CANCEL:
            log.info("MainWindow - on_saveas_project_clicked - cancelled: FileChooserAction.OPEN")
        # Destroy dialog
        open_dialog.destroy()
        
    def on_project_settings_clicked(self, button):
        """Display dialog to input project settings"""
        log.info('onProjectSettingsClicked - Launch project settings')
        # Handle project settings window
        view.project.ProjectSettings(self.window, self.sch_database)
                                                        
    def on_program_settings_clicked(self, button):
        """Display dialog to input project settings"""
        log.info('onProjectSettingsClicked - Launch project settings')
        # Handle project settings window
        view.project.ProgramSettings(self.window,
                                     self.sch_database, 
                                     self.program_settings,
                                     self.user_library_dir)
        with open(self.settings_filename, 'wb') as fp:
            pickle.dump(self.program_settings, fp)
            
    def on_export_project_clicked(self, widget):
        """Export project to spreadsheet"""

        def exec_func(progress, filename):
            # Create new spreadsheet
            spreadsheet = misc.Spreadsheet()
            # Export schedule
            progress.add_message('Exporting Schedule Items...')
            progress.set_fraction(0)
            self.sch_database.export_sch_spreadsheet(spreadsheet)
            # Export Resources
            progress.add_message('Exporting Resource Items...')
            progress.set_fraction(0.1)
            self.sch_database.export_res_spreadsheet(spreadsheet)
            # Export Resource usage
            progress.add_message('Exporting Resource Usage...')
            progress.set_fraction(0.2)
            self.sch_database.export_res_usage_spreadsheet(spreadsheet)
            # Export analysis of rates
            progress.add_message('Exporting Analysis of Rates...')
            progress.set_fraction(0.3)
            self.sch_database.export_ana_spreadsheet(spreadsheet, progress, [0.3,0.9])
            # Save spreadsheet
            progress.add_message('Saving spreadsheet...')
            progress.set_fraction(0.9)
            spreadsheet.save(filename)
            progress.set_fraction(1)
            progress.add_message('<b>Export Successful</b>')
            progress.pulse(end=True)
            
        # Setup file save dialog
        dialog = Gtk.FileChooserDialog("Save spreadsheet as...", self.window,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_SAVE, Gtk.ResponseType.ACCEPT))
        file_filter = self.builder.get_object("Spreadsheet")
        dialog.set_current_name('untitled.xlsx')
        dialog.add_filter(file_filter)
        
        # Run dialog and evaluate code
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            dialog.destroy()
            # Setup progress dialog
            self.run_command(exec_func, filename)
            self.display_status(misc.INFO, "Project exported to spreadsheet")
            log.info('MainWindow - on_export_project_clicked - File saved as - ' + filename)
        elif response == Gtk.ResponseType.CANCEL:
            dialog.destroy()
            self.display_status(misc.WARNING, "Project export cancelled by user")
            log.info('MainWindow - on_export_project_clicked - Cancelled')

    def on_infobar_close(self, widget, response=0):
        """Hides the infobar"""
        infobar_revealer = self.builder.get_object("infobar_revealer")
        infobar_revealer.set_reveal_child(False)

    def on_redo_clicked(self, button):
        """Redo action from stack"""
        if self.stack.canredo():
            log.info(self.stack.redotext())
            self.display_status(misc.INFO, self.stack.redotext())
            self.stack.redo()
            self.update()
        else:
            self.display_status(misc.INFO, "Nothing left to Redo")

    def on_undo_clicked(self, button):
        """Undo action from stack"""
        if self.stack.canundo():
            log.info(self.stack.undotext())
            self.display_status(misc.INFO, self.stack.undotext())
            self.stack.undo()
            self.update()
        else:
            self.display_status(misc.INFO, "Nothing left to Undo")

    # Schedule signal handler methods

    def on_sch_add_clicked(self, button):
        """Add empty row to schedule view"""
        items = self.sch_dialog.run()
        if items:
            self.schedule_view.add_item_at_selection(items)
            # Refresh resource view to update any items that may be added
            self.resource_view.update_store()
            
    def on_sch_add_item_clicked(self, button):
        """Add empty row to schedule view"""
        item = data.schedule.ScheduleItemModel(code = '1.1',
                                              description = '',
                                              unit = '',
                                              rate = 0,
                                              qty = 0,
                                              remarks = '',
                                              ana_remarks = '',
                                              category = None,
                                              parent = None)
        self.schedule_view.add_item_at_selection([item])
        
    def on_sch_add_sub_item_clicked(self, button):
        """Add empty row to schedule view"""
        item = data.schedule.item = data.schedule.ScheduleItemModel(code = '1.1',
                                              description = '',
                                              unit = 'Unit',
                                              rate = 0,
                                              qty = 0,
                                              remarks = '',
                                              ana_remarks = '',
                                              category = None,
                                              parent = 'UNSET')
        self.schedule_view.add_item_at_selection([item])
        
    def on_sch_add_category_clicked(self, button):
        """Add empty row to schedule view"""
        newcat = self.sch_database.get_new_schedule_category_name()
        paths = self.schedule_view.add_category_at_selection(newcat)
        
    def on_sch_edit_clicked(self, button):
        """Edit analysis"""
        codes = self.schedule_view.get_selected_codes()
        if codes:
            code = codes[0]
            model = self.sch_database.get_item(code, modify_res_code=False)
            if model.unit != '':
                dialog_ana = self.analysis_view.init(model)
                # Show stack page
                self.hidden_stack.set_visible_child_name('Analysis')
                self.analysis_view.tree.grab_focus()
                return
        self.display_status(misc.WARNING, "No valid item selected for editing")
            
    def on_sch_mark_clicked(self, button):
        """Add empty row to schedule view"""
        self.schedule_view.update_store(mark=True)
        self.display_status(misc.INFO, "Items with rate mismatch marked")
        
    def on_sch_refresh_clicked(self, button):
        ret_code = self.schedule_view.update_selected_rates()
        if ret_code:
            self.display_status(misc.INFO, "Rates updated")
        elif ret_code is None:
            self.display_status(misc.WARNING, "No valid items in selection")
        else:
            self.display_status(misc.ERROR, "An error occured while updating rates")
            
    def on_sch_renumber_clicked(self, button):
        self.sch_database.assign_auto_item_numbers()
        self.schedule_view.update_store()
                
    def on_sch_res_usage_clicked(self, button):
        view.resource.ResourceUsageDialog(self.window, self.sch_database).run()

    def on_schedule_delete_clicked(self, button):
        """Delete selected rows from schedule view"""
        self.schedule_view.delete_selected_items()
        log.info('MainWindow - on_schedule_delete_clicked - Selected items deleted')

    def on_copy_schedule(self, button):
        """Copy selected rows from schedule view to clipboard"""
        self.schedule_view.copy_selection()

    def on_paste_schedule(self, button):
        """Paste rows from clipboard into schedule view"""
        self.schedule_view.paste_at_selection()

    def on_import_res_clicked(self, button):
        """Imports resources from spreadsheet selected by 'filechooserbutton_res' into resource view"""
        filename = self.builder.get_object("filechooserbutton_res").get_filename()
        
        columntypes = [str, str, str, float, float, float, str, str]
        captions = ['Code.', 'Description', 'Unit', 'Rate', 'VAT', 'Discount', 
                    'Remarks', 'Category']
        widths = [80,200,80,80,80,80,100,100]
        expandables = [False,True,False,False,False,False,False,False]
        
        spreadsheet_dialog = misc.SpreadsheetDialog(self.window, filename, columntypes, captions, [widths, expandables])
        models = spreadsheet_dialog.run()
        
        items = []
        resources = []
        for index, model in enumerate(models):
            if model[0] != '' and model[1] != '' and model[2] != '':
                reference = model[6] if model[6] != '' else None
                category = model[7] if model[7] != '' else None
                try:
                    rate = Decimal(model[3])
                    vat = Decimal(model[4])
                    discount = Decimal(model[5])
                    res = data.schedule.ResourceItemModel(code = model[0],
                                        description = model[1],
                                        unit = model[2],
                                        rate = rate,
                                        vat = vat,
                                        discount = discount,
                                        reference = reference,
                                        category = category)
                    resources.append(res)
                except:
                    log.warning('MainWindow - on_import_res_clicked - Error in data' + str(index))
        self.sch_database.insert_resource_multiple(resources)
        self.display_status(misc.INFO, str(index)+' records processed')
        log.info('MainWindow - on_import_res_clicked - data added - ' + str(index) + ' records')
        
        self.update()

    def on_import_sch_clicked(self, button):
        """Imports schedule from spreadsheet selected by 'filechooserbutton_schedule' into schedule view"""
        filename = self.builder.get_object("filechooserbutton_schedule").get_filename()

        columntypes = [str, str, str, float, float, float, str]
        captions = ['Code.', 'Description', 'Unit', 'Rate', 'Qty', 'Amount',
                    'Remarks']
        widths = [80, 200, 80, 80, 80, 80, 100]
        expandables = [False, True, False, False, False, False, False]

        spreadsheet_dialog = misc.SpreadsheetDialog(self.window, filename, columntypes, captions, [widths, expandables])
        models = spreadsheet_dialog.run()

        category = None
        id_parent = None
        id_cur_item = None
        items = []
        
        if models:
            for index, model in enumerate(models):
                
                # If category
                if model[0] != '' and model[1] != '' and model[2] == '' and model[0].count('.') == 0 and model[1].upper() == model[1]:
                    code = model[0]
                    desc = model[1]
                    category = desc
                
                # If parent item
                elif model[0] != '' and model[1] != '' and model[0].count('.') in [0,1]:
                    code = model[0]
                    try:
                        rate = Decimal(model[3])
                        qty = Decimal(model[4])
                    except:
                        log.warning('MainWindow - on_import_sch_clicked - Error in data - ' + str(index))
                        rate = Decimal(0)
                        qty = Decimal(0)
                    sch = data.schedule.ScheduleItemModel(code = code,
                                                          description = model[1],
                                                          unit = model[2],
                                                          rate = rate,
                                                          qty = qty,
                                                          remarks = model[5],
                                                          category = category,
                                                          parent = None)
                    id_parent = code
                    id_cur_item = code
                    items.append(sch)
                
                # If sub item
                elif model[0] != '' and model[1] != '' and model[0].count('.') in [1, 2] and id_parent is not None:
                    code = model[0]
                    try:
                        rate = Decimal(model[3])
                        qty = Decimal(model[4])
                    except:
                        log.warning('MainWindow - on_import_sch_clicked - Error in data - ' + str(index))
                        rate = Decimal(0)
                        qty = Decimal(0)
                    sch = data.schedule.ScheduleItemModel(code = code,
                                                          description = model[1],
                                                          unit = model[2],
                                                          rate = rate,
                                                          qty = qty,
                                                          remarks = model[5],
                                                          category = category,
                                                          parent = id_parent)
                    id_cur_item = code
                    items.append(sch)
                        
            self.sch_database.insert_item_multiple(items)
            self.display_status(misc.INFO, str(index)+' records processed')
            log.info('MainWindow - on_import_sch_clicked - data added - ' + str(index) + ' records')
            
            self.update()
        else:
            log.info('MainWindow - on_import_sch_clicked - cancelled')
        
    def on_import_ana_clicked(self, button):
        """Imports analysis from spreadsheet selected by 'filechooserbutton_schedule' and links it into schedule view"""
        filename = self.builder.get_object("filechooserbutton_schedule").get_filename()

        columntypes = [str, str, str, float, float, float]
        captions = ['Code.', 'Description', 'Unit', 'Rate', 'Qty', 'Amount']
        widths = [80, 200, 80, 80, 80, 80]
        expandables = [False, True, False, False, False, False]

        # Setup spreadsheet dialog
        spreadsheet_dialog = misc.SpreadsheetDialog(self.window, filename, columntypes, captions, [widths, expandables])
        models = spreadsheet_dialog.run()

        if models:
            
            # Import Analysis in external thread
            def exec_func(progress, models):
                index = 0
                
                while index < len(models):
                    item = data.schedule.ScheduleItemModel(None,None)
                    index = data.schedule.parse_analysis(models, item, index, True)
                    # Get item with corresponding code from database
                    sch_item = self.sch_database.get_item(item.code)
                    if sch_item:
                        # Copy values to imported item
                        item.description = sch_item.description
                        item.unit = sch_item.unit
                        item.rate = sch_item.rate
                        item.qty = sch_item.qty
                        item.category = sch_item.category
                        item.remarks = sch_item.remarks
                        item.parent = sch_item.parent
                        # Update item in database
                        self.sch_database.update_item_atomic(item)
                        progress.add_message('Analysis for Item No.' + item.code + ' imported')
                        log.info('MainWindow - on_import_ana_clicked - analysis added - ' + str(item.code))
                    else:
                        progress.add_message("<span foreground='#FF0000'>Item No." + str(item.code) + ' not found in schedule items</span>')
                        log.warning('MainWindow - on_import_ana_clicked - analysis not added - code not found - ' + str(item.code))
                    # Update fraction
                    progress.set_fraction(index/len(models))
            
            self.run_command(exec_func, models)
    
        # Clear undo stack
        self.stack.clear()
        
            
    # Analysis signal handler methods
    
    def on_ana_undo(self, widget):
        """Undo action from stack"""
        self.analysis_view.on_undo()

    def on_ana_redo(self, widget):
        """Redo action from stack"""
        self.analysis_view.on_redo()

    def on_ana_copy(self, widget):
        """Copy selected row to clipboard"""
        self.analysis_view.on_copy()
    
    def on_ana_paste(self, widget):
        """Paste copied item at selected row"""
        self.analysis_view.on_paste()
        
    def ana_add_res_library(self, widget):
        self.analysis_view.add_res_library(self.res_select_dialog)

    def ana_add_res(self, widget):
        self.analysis_view.add_res()

    def ana_add_res_group(self, widget):
        self.analysis_view.add_res_group()

    def ana_add_sum(self, widget):
        self.analysis_view.add_sum()

    def ana_add_weight(self, widget):
       self.analysis_view.add_weight()

    def ana_add_times(self, widget):
        self.analysis_view.add_times()

    def ana_add_round(self, widget):
        self.analysis_view.add_round()

    def ana_delete_selected_row(self, widget):
        """Delete selected rows"""
        self.analysis_view.delete_selected_row()
        
    def on_import_clicked(self, button):
        """Imports analysis from selected spreadsheet into analysis view"""
        filename = self.builder.get_object("filechooserbutton_ana").get_filename()
        self.analysis_view.on_import_clicked(filename)
        
    @undoable
    def on_ana_save(self, button):
        # Show stack default page
        self.hidden_stack.set_visible_child_name('Default')
        model_ret = self.analysis_view.exit()
        old_item = self.sch_database.get_item(model_ret.code)
        self.sch_database.update_item(model_ret)
        # Refresh resource view to update any items that may be added
        self.resource_view.update_store()
        
        yield "Modify schedule item of code:'{}'".format(str(old_item.code))
        self.sch_database.update_item(old_item)
        
    def on_ana_cancel(self, button):
        # Show stack default page
        self.hidden_stack.set_visible_child_name('Default')
            
    # Resource signal handler methods
    
    def on_res_add_clicked(self, button):
        """Add empty row to schedule view"""
        self.resource_view.add_resource_at_selection()
        
    def on_res_add_category_clicked(self, button):
        """Add empty category to schedule view"""
        newcat = self.sch_database.get_new_resource_category_name()
        self.resource_view.add_category_at_selection(newcat)
        
    def on_res_load_rates_clicked(self, button):
        """Add empty row to schedule view"""
        dialog = view.resource.SelectResourceDialog(self.window, 
                                self.sch_database, 
                                select_database_mode=True)
        databasename = dialog.run()
        self.sch_database.update_resource_from_database(databasename)
        self.resource_view.update_store()

    def on_res_delete_clicked(self, button):
        """Delete selected rows from schedule view"""
        self.resource_view.delete_selected_item()
        log.info('MainWindow - on_schedule_delete_clicked - Selected items deleted')

    def on_copy_res(self, button):
        """Copy selected rows from schedule view to clipboard"""
        self.resource_view.copy_selection()

    def on_paste_res(self, button):
        """Paste rows from clipboard into schedule view"""
        self.resource_view.paste_at_selection()

    # General signal handler methods

    def on_refresh(self, widget):
        """Refresh display of views"""
        log.info('on_refresh called')
        self.update()

    def __init__(self):
        log.info('MainWindow - Initialising')

        # Check for project active status
        self.project_active = False
        # Open temporary file for database
        (temp_fpointer, self.filename_temp) = tempfile.mkstemp(prefix=misc.PROGRAM_NAME+'_tempproj_')
        
        log.info('Setting up main Database')
        # Setup schedule database    
        self.sch_database = data.schedule.ScheduleDatabase()
        self.sch_database.create_new_database(self.filename_temp)
        log.info('Database initialised')
        
        log.info('Setting up program settings')
        dirs = appdirs.AppDirs(misc.PROGRAM_NAME, misc.PROGRAM_AUTHOR, version=misc.PROGRAM_VER)
        settings_dir = dirs.user_data_dir
        self.user_library_dir = misc.posix_path(dirs.user_data_dir,'database')
        self.settings_filename = misc.posix_path(settings_dir,'settings.ini')
        
        # Create directory if does not exist
        if not os.path.exists(settings_dir):
            os.makedirs(settings_dir)
        if not os.path.exists(self.user_library_dir):
            os.makedirs(self.user_library_dir)
        
        try:
            if os.path.exists(self.settings_filename):
                with open(self.settings_filename, 'rb') as fp:
                    self.program_settings = pickle.load(fp)
                    log.info('Program settings opened at ' + str(self.settings_filename))
            else:
                self.program_settings = copy.deepcopy(misc.default_program_settings)
                with open(self.settings_filename, 'wb') as fp:
                    pickle.dump(self.program_settings, fp)
                log.info('Program settings saved at ' + str(self.settings_filename))
        except:
            # If an error load default program preference
            self.program_settings = copy.deepcopy(misc.default_program_settings)
        log.info('Program settings initialised')
        
        log.info('Setting up Libraries')
        
        # Add default path
        file_names = os.listdir(misc.abs_path('database'))
        library_names = []
        for f in file_names:
            if f[-len(misc.PROJECT_EXTENSION):].lower() == misc.PROJECT_EXTENSION:
                library_names.append(misc.abs_path('database',f))
        
        # Add user datapath
        file_names = os.listdir(self.user_library_dir)
        for f in file_names:
            if f[-len(misc.PROJECT_EXTENSION):].lower() == misc.PROJECT_EXTENSION:
                library_names.append(misc.posix_path(self.user_library_dir,f))
                
        for library_name in library_names:
            if self.sch_database.add_library(library_name):
                log.info('MainWindow - ' + library_name + ' - added')
            else:
                log.warning('MainWindow - ' + library_name + ' - not added')

        log.info('Library initialisation complete')
        
        # Initialise undo/redo stack
        self.stack = undo.Stack()
        undo.setstack(self.stack)
        # Save point in stack for checking change state
        self.stack.savepoint()

        # Other variables
        self.filename = None

        # Setup main window
        self.builder = Gtk.Builder()
        self.builder.add_from_file(misc.abs_path("interface", "mainwindow.glade"))
        self.window = self.builder.get_object("window_main")
        self.builder.connect_signals(self)
        
        # Initialise resource view
        box_res = self.builder.get_object("box_res")
        self.resource_view = view.resource.ResourceView(self.window, self.sch_database, box_res)

        # Initialise schedule view
        box_sch = self.builder.get_object("box_sch")
        self.schedule_view = view.schedule.ScheduleView(self.window, self.sch_database, box_sch, show_sum=True)
        
        # Initialise analysis view
        self.hidden_stack = self.builder.get_object("hidden_stack")
        self.analysis_tree = self.builder.get_object("treeview_analysis")
        self.analysis_remark_entry = self.builder.get_object("entry_analysis_remarks")
        self.analysis_view = view.analysis.AnalysisView(self.window, 
                                                        self.analysis_tree, 
                                                        self.analysis_remark_entry, 
                                                        self.sch_database,
                                                        self.program_settings)
        
        self.window.show_all()
        
        # Setup schedule dialog for selecting database items
        log.info('Setting up Dialog windows')
        self.sch_dialog = view.schedule.SelectScheduleDialog(self.window, self.sch_database, self.program_settings)
        self.res_select_dialog = view.resource.SelectResourceDialog(self.window, self.sch_database)
        log.info('Dialog windows initialised')
        
        
class MainApp(Gtk.Application):
    """Class handles application related tasks"""

    def __init__(self, *args, **kwargs):
        log.info('MainApp - Start initialisation')
        
        super().__init__(*args, application_id="org.estimator.mainapp",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
                         **kwargs)
                         
        self.window = None
        self.about_dialog = None
        self.windows = []
        
        self.add_main_option("test", ord("t"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Command line test", None)
                             
        log.info('MainApp - Initialised')
        

    # Application function overloads
    
    def do_startup(self):
        log.info('MainApp - do_startup - Start')
        
        Gtk.Application.do_startup(self)
        
        action = Gio.SimpleAction.new("new", None)
        action.connect("activate", self.on_new)
        self.add_action(action)
        
        action = Gio.SimpleAction.new("help", None)
        action.connect("activate", self.on_help)
        self.add_action(action)

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.on_about)
        self.add_action(action)

        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit)
        self.add_action(action)

        builder = Gtk.Builder.new_from_string(misc.MENU_XML, -1)
        self.set_app_menu(builder.get_object("app-menu"))
        
        log.info('MainApp - do_startup - End')
    
    def do_activate(self):
        log.info('MainApp - do_activate - Start')
        
        self.window = MainWindow()
        self.windows.append(self.window)
        self.add_window(self.window.window)
        self.window.window.show()
        
        log.info('MainApp - do_activate - End')
        
    def do_open(self, files, hint):
        log.info('MainApp - do_open - Start')
        self.activate()
        if len(files) > 1:
            filename = files[0].get_path()
            self.window.on_open_project_clicked(None, filename)
            log.info('MainApp - do_open  - opnened file ' + filename)
        log.info('MainApp - do_open  - End')
        return 0
    
    def do_command_line(self, command_line):
        log.info('MainApp - do_command_line - Start')
        options = command_line.get_arguments()
        self.activate()
        if len(options) > 1:
            self.window.on_open_project_clicked(None, options[1])
        log.info('MainApp - do_command_line - End')
        return 0
        
    # Application callbacks
        
    def on_about(self, action, param):
        """Show about dialog"""
        log.info('MainApp - Show About window')
        # Setup about dialog
        self.builder = Gtk.Builder()
        self.builder.add_from_file(misc.abs_path("interface", "aboutdialog.glade"))
        self.about_dialog = self.builder.get_object("aboutdialog")
        self.about_dialog.set_transient_for(self.get_active_window())
        self.about_dialog.set_modal(True)
        self.about_dialog.run()
        self.about_dialog.destroy()
        
    def on_help(self, action, param):
        """Launch help file"""
        log.info('onHelpClick - Launch Help file')
        misc.open_file(misc.abs_path('documentation', 'manual.pdf'))
        
    def on_new(self, action, param):
        """Launch a new instance of the application"""
        log.info('MainApp - Raise new window')
        self.do_activate()
        
    def on_quit(self, action, param):
        self.quit()
        
