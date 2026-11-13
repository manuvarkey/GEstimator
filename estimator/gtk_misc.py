"""Legacy GTK widgets, loaded on demand."""
from .misc import *
from gi.repository import Gtk, Gdk, GLib, GObject, Pango

class CellTextView(Gtk.TextView, Gtk.CellEditable):

    __gproperties__ = {
         'editing-canceled': (bool, 'editing-canceled', 'Inheritedproperty', False,
                  GObject.PARAM_READWRITE)
    }

    property_names = __gproperties__.keys()

    def __init__(self):
        super().__init__()

    def set_text(self, text):
        text_buffer = self.get_buffer()
        text_buffer.set_text(text)

    def get_text(self, *args):
        text_buffer = self.get_buffer()
        start = text_buffer.get_start_iter()
        end   = text_buffer.get_end_iter()
        return text_buffer.get_text(start, end, True)

    def do_editing_done(*args):
        pass

    def do_remove_widget(*args):
        pass

    def do_start_editing(*args):
        pass


class CellRendererMultilineText(Gtk.CellRendererText):

     def __init__(self):
         Gtk.CellRendererText.__init__(self)
         self.set_property('mode',  Gtk.CellRendererMode.EDITABLE)

     def __getattr__(self, name):
         try:
             return self.get_property(name)
         except TypeError:
             raise AttributeError

     def __setattr__(self, name, value):
         try:
             self.set_property(name, value)
         except TypeError:
             self.__dict__[name] = value

     def do_get_property(self, property):
         if property.name not in self.property_names:
             raise TypeError('No property named %s' % (property.name,))
         return self.__dict__[property.name]

     def do_set_property(self, property, value):
         if property.name not in self.property_names:
             raise TypeError('No property named %s' % (property.name,))
         self.__dict__[property.name] = value

     def do_start_editing(self, event, widget, path, bg_area, cell_area, flags):

         editor = CellTextView()
         editor.set_wrap_mode(Gtk.WrapMode.WORD)
         editor.props.accepts_tab = False
         editor.connect('key-press-event', self.on_key_press_event, path)

         if self.text:
             editor.set_text(self.text)

         editor.grab_focus()
         editor.show()

         return editor

     def on_key_press_event(self, widget, event, path):
         '''Catch pressing Enter keys.

         Shift, Ctrl or Alt combined with Return or Keypad Enter can be used
         for linebreaking. Pressing Return or Keypad Enter alone will finish
         editing.'''

         mask     = event.state
         keyname = Gdk.keyval_name(event.keyval)

         accel_masks    = (Gdk.ModifierType.CONTROL_MASK | \
                           Gdk.ModifierType.SHIFT_MASK | \
                           Gdk.ModifierType.MOD1_MASK)
         enter_keynames = ('Return', 'KP_Enter')

         if (keyname in enter_keynames) and not (mask & accel_masks):
             self.emit('edited', path, widget.get_text())
             widget.destroy()


class UserEntryDialog():
    """Creates a dialog box for entry of custom data fields

        Arguments:
            parent: Parent Window
            window_caption: Window Caption to be displayed on Dialog
            item_values: Item values to be requested from user
            item_captions: Description of item values to be shown to user
    """

    def __init__(self, parent, window_caption, item_values, item_captions):
        self.toplevel = parent
        self.entrys = []
        self.item_values = item_values
        self.item_captions = item_captions

        self.dialog_window = Gtk.Dialog(window_caption, parent, Gtk.DialogFlags.MODAL,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OK, Gtk.ResponseType.OK))
        self.dialog_window.set_title(window_caption)
        self.dialog_window.set_resizable(True)
        self.dialog_window.set_border_width(5)
        self.dialog_window.set_size_request(int(self.toplevel.get_size_request()[0]*0.8),-1)
        self.dialog_window.set_default_response(Gtk.ResponseType.OK)

        # Pack Dialog
        dialog_box = self.dialog_window.get_content_area()
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.set_row_spacing(5)
        grid.set_border_width(5)
        grid.set_hexpand(True)
        dialog_box.add(grid)
        for caption in self.item_captions:
            # Captions
            user_label = Gtk.Label(caption)
            user_label.set_halign(Gtk.Align.END)
            # Text Entry
            user_entry = Gtk.Entry()
            user_entry.set_hexpand(True)
            user_entry.set_activates_default(True)
            # Pack Widgets
            grid.attach_next_to(user_label, None, Gtk.PositionType.BOTTOM, 1, 1)
            grid.attach_next_to(user_entry, user_label, Gtk.PositionType.RIGHT, 1, 1)
            self.entrys.append(user_entry)
        # Add data
        for value, user_entry in zip(self.item_values, self.entrys):
            user_entry.set_text(value)

    def run(self):
        """Display dialog box and modify Item Values in place

            Save modified values to "item_values" (item passed by reference)
            if responce is Ok. Discard modified values if response is Cancel.

            Returns:
                True on Ok
                False on Cancel
        """
        # Run dialog
        self.dialog_window.show_all()
        response = self.dialog_window.run()

        if response == Gtk.ResponseType.OK:
            # Get formated text and update item_values
            for key, user_entry in zip(range(len(self.item_values)), self.entrys):
                cell = user_entry.get_text()
                try:  # try evaluating string
                    if type(self.item_values[key]) is str:
                        cell_formated = str(cell)
                    elif type(self.item_values[key]) is int:
                        cell_formated = str(float(cell))
                    elif type(self.item_values[key]) is float:
                        cell_formated = str(int(cell))
                    else:
                        cell_formated = ''
                except:
                    cell_formated = ''
                self.item_values[key] = cell_formated

            self.dialog_window.destroy()
            return True
        else:
            self.dialog_window.destroy()
            return False


class SpreadsheetDialog:
    """Dialog for manage input and output of spreadsheets"""

    def __init__(self, parent, filename, columntypes, captions, dimensions = None, allow_formula=False):
        """Initialise SpreadsheetDialog class

            Arguments:
                parent: Parent widget (Main window)
                filename:
                columntypes: Data types of columns.
                             Takes following values:
                                misc.MEAS_NO: Integer
                                misc.MEAS_L: Float
                                misc.MEAS_DESC: String
                                misc.MEAS_CUST: Value omited
                dimensions: List of two lists passing column widths and expand properties
                allow_formula: Reads all values as string
        """
        log.info('SpreadsheetDialog - Initialise')
        # Setup variables
        self.parent = parent
        self.filename = filename
        self.captions = captions
        self.columntypes = columntypes
        self.dimensions = dimensions
        self.allow_formula = allow_formula

        self.top = 0
        self.bottom = 0
        self.left = 0
        self.right = 0
        self.values = []
        self.spreadsheet = None
        self.sheet = ''

        # Setup dialog window
        self.builder = Gtk.Builder()
        self.builder.add_from_file(abs_path("interface","spreadsheetdialog.glade"))
        self.window = self.builder.get_object("dialog")
        self.window.set_transient_for(self.parent)
        self.window.set_default_size(1100,600)
        self.builder.connect_signals(self)

        # Get required objects
        self.combo = self.builder.get_object("combobox_sheet")
        self.combo_store = self.builder.get_object("liststore_combo")
        self.tree = self.builder.get_object("treeview_schedule")
        self.entry_top = self.builder.get_object("entry_top")
        self.entry_bottom = self.builder.get_object("entry_bottom")
        self.entry_left = self.builder.get_object("entry_left")
        self.entry_right = self.builder.get_object("entry_right")

        # Setup treeview
        self.columns = []
        self.cells = []
        # Setup row number column
        cell_row = Gtk.CellRendererText()
        column_row = Gtk.TreeViewColumn('', cell_row)
        column_row.add_attribute(cell_row, "markup", 0)
        column_row.set_min_width(50)
        column_row.set_fixed_width(50)
        cell_row.props.wrap_width = 50
        cell_row.props.background = MEAS_COLOR_LOCKED
        self.cells.append(cell_row)
        self.columns.append(column_row)
        self.tree.append_column(column_row)
        # Setup remaining columns
        for c_no, caption  in enumerate(self.captions,1):
            cell = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(caption, cell)
            column.props.sizing = Gtk.TreeViewColumnSizing.AUTOSIZE
            column.connect("notify", self.on_wrap_column_resized, cell)
            column.add_attribute(cell, "text", c_no)
            self.cells.append(cell)
            self.columns.append(column)
            self.tree.append_column(column)
        # Setup dimensions
        if dimensions is not None:
            self.setup_column_props(*dimensions)
        # Setup liststore model
        types = [str] + [str]*len(self.columntypes)
        self.store = Gtk.ListStore(*types)
        self.tree.set_model(self.store)
        # Misc options
        self.tree.set_grid_lines(3)
        self.tree.set_enable_search(True)
        search_cols = [no for no,x in enumerate(self.columntypes,1) if x == str]
        self.tree.set_search_equal_func(self.equal_func, [0,1,2,3])

        # Read file into spreadsheet object
        if filename is not None:
            try:
                self.spreadsheet = Spreadsheet(filename)
            except:
                self.spreadsheet = None
                log.warning('SpreadsheetDialog - Spreadsheet could not be read - ' + filename)

        # Setup combobox
        if self.spreadsheet:
            sheets = self.spreadsheet.sheets()
            for sheet in sheets:
                self.combo_store.append([sheet])
            if sheets:
                self.combo.set_active_id(sheets[0])
                self.update()


    def run(self):
        """Display dialog box and return data model

            Returns:
                Data Model on Ok
                [] on Cancel
        """
        self.window.show_all()
        response = self.window.run()
        self.window.destroy()

        if response == 1 and self.spreadsheet:
            log.info('SpreadsheetDialog - run - Response Ok')
            return self.values
        else:
            log.info('SpreadsheetDialog - run - Response Cancel')
            return []

    def update(self):
        """Update contents from input values"""
        log.info('SpreadsheetDialog - Update')

        # Read if sheet changed
        sheet = self.combo_store[self.combo.get_active_iter()][0]
        if sheet != self.sheet:
            self.sheet = sheet
            self.spreadsheet.set_active_sheet(self.sheet)
            self.entry_top.set_text('1')
            self.entry_bottom.set_text(str(self.spreadsheet.length()+1))
            self.entry_left.set_text('1')

        # Read values of entries
        self.top = int(self.entry_top.get_text())
        self.bottom = int(self.entry_bottom.get_text())
        self.left = int(self.entry_left.get_text())

        # Set values
        self.entry_right.set_text(str(self.left + len(self.columntypes)))

        # Read spreadsheet
        self.values = self.spreadsheet.read_rows(self.columntypes, start=self.top-1, end=self.bottom-1, left=self.left-1, allow_formula=self.allow_formula)

        # Update store
        self.store.clear()
        for slno, value in enumerate(self.values, self.top):
            formated_value = [str(x) if x != 0 else '' for x in value]
            self.store.append(['<b>' + str(slno) + '</b>'] + formated_value)

    def setup_column_props(self, widths, expandables):
        """Set column properties
            Arguments:
                widths: List of column widths type-> [int, ...]. None values are skiped.
                expandables: List of expand property type-> [bool, ...]. None values are skiped.
        """
        for column, cell, width, expandable in zip(self.columns[1:], self.cells[1:], widths, expandables):
            if width != None:
                column.set_min_width(width)
                column.set_fixed_width(width)
                cell.props.wrap_width = width
            if expandable != None:
                column.set_expand(expandable)

    def equal_func(self, model, column, key, iter, cols):
        """Equal function for interactive search"""
        search_string = ''
        for col in cols:
            search_string += ' ' + model[iter][col].lower()
        for word in key.split():
            if word.lower() not in search_string:
                return True
        return False

    def on_wrap_column_resized(self, column, pspec, cell):
        """ Automatically adjust wrapwidth to column width"""

        width = column.get_width() - 5
        oldwidth = cell.props.wrap_width

        if width > 0 and width != oldwidth:
            cell.props.wrap_width = width
            # Force redraw of treeview
            GLib.idle_add(column.queue_resize)

    # Callbacks

    def onRefreshClicked(self, button):
        """Refresh screen on button click"""

        # Sanitise entries
        if self.entry_top.get_text() == '':
            self.entry_top.set_text('1')
        if self.entry_bottom.get_text() == '':
            self.entry_bottom.set_text('1')
        if self.entry_left.get_text() == '':
            self.entry_left.set_text('1')

        if self.spreadsheet:
            self.update()

    def onEntryEditedNum(self, entry):
        """Treeview cell renderer for editable number field

            User Data:
                column: column in ListStore being edited
        """
        new_text = entry.get_text()
        num = ''
        if new_text != '':
            try:  # check whether item evaluates fine
                num = int(new_text)
                if num <= 0:
                   num = 1
            except:
                log.warning("SpreadsheetDialog - onEntryEditedNum - evaluation of ["
                + new_text + "] failed")
        entry.set_text(str(num))


class ProgressWindow:
    """Class for handling display of long running proccess"""

    def __init__(self, parent=None, label=None, progress=None):

        self.parent = parent
        self.label = label
        self.progress = progress
        # Setup data
        self.step = 0
        self.fraction = 0

        # Setup progress indicator window
        if parent:
            self.dialog = Gtk.Window(default_height=250, default_width=400,
                                     title='Process running...')
            self.dialog.set_transient_for(self.parent)
            self.dialog.set_gravity(Gdk.Gravity.CENTER)
            self.dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
            self.dialog.set_modal(True)
            self.dialog.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_margin_left(6)
            box.set_margin_right(6)

            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            self.store = Gtk.ListStore(str)
            self.tree = Gtk.TreeView.new_with_model(self.store)
            column = Gtk.TreeViewColumn("Message")
            cell = Gtk.CellRendererText()
            column.pack_start(cell, True)
            column.add_attribute(cell, "markup", 0)
            self.tree.append_column(column)
            scroll.add(self.tree)

            box.pack_start(scroll, True, True, 3)
            self.progress = Gtk.ProgressBar()
            box.pack_start(self.progress, False, False, 3)
            dismiss = Gtk.Button('Dismiss')
            box.pack_start(dismiss, False, False, 3)
            self.dialog.add(box)

            # Connect events
            self.dialog.connect("delete-event",self.on_delete)
            dismiss.connect("clicked",self.on_dismiss)

    # Window functions

    def show(self):
        def callback():
            self.dialog.show_all()
            return False
        GLib.idle_add(callback)

    def close(self):
        self.dialog.close()

    def on_delete(self, *args):
        if self.fraction == 1:
            return False
        else:
            # Cancel event
            self.dialog.hide()
            return True

    def on_dismiss(self, button):
        if self.fraction == 1:
            self.close()
        else:
            self.dialog.hide()

    # General functions

    def set_pulse_step(self, width):
        self.step = width
        self.fraction = 0

    def set_fraction(self, fraction):
        def callback():
            self.fraction = fraction
            self.progress.set_fraction(self.fraction)
            if self.parent:
                self.show()
            return False
        GLib.idle_add(callback)

    def pulse(self, end=False):
        def callback():
            self.fraction += self.step
            if end:
                if self.parent:
                    self.fraction = 1
                    self.dialog.set_title('Process Complete')
                    self.show()
                else:
                    pass
            self.progress.set_fraction(self.fraction)
            return False
        GLib.idle_add(callback)

    def add_message(self, message):
        if self.parent:
            def callback():
                itemiter = self.store.append([message])
                path = self.store.get_path(itemiter)
                self.tree.scroll_to_cell(path)
                return False
            GLib.idle_add(callback)
        else:
            GLib.idle_add(self.label.set_markup, message)


class SplashScreen:
    def __init__(self, callback, image_filename, min_splash_time=0 ):
        self.image = Gtk.Image.new_from_file(image_filename )
        self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
        self.window.set_gravity(Gdk.Gravity.CENTER)
        self.window.set_auto_startup_notification(False)
        self.window.set_decorated(False)
        self.window.add(self.image)
        self.min_splash_time   = time.time() + min_splash_time
        self.window.show_all()
        GLib.timeout_add_seconds(1, callback)

    def exit(self):
        # Make sure the minimum splash time has elapsed
        timeNow = time.time()
        if timeNow < self.min_splash_time:
            time.sleep( self.min_splash_time - timeNow )

        # Destroy the splash window
        self.window.destroy( )


def get_user_input_text(parent, message, title='', oldval=None, multiline=False):
    '''Gets a single user input by diplaying a dialog box

    Arguments:
        parent: Parent window
        message: Message to be displayed to user
        title: Dialog title text
        multiline: Allows multiline input is True
    Returns:
        Returns user input as a string or 'None' if user does not input text.
    '''
    dialogWindow = Gtk.MessageDialog(parent,
                                     Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                     Gtk.MessageType.QUESTION,
                                     Gtk.ButtonsType.OK_CANCEL,
                                     message)

    dialogWindow.set_transient_for(parent)
    dialogWindow.set_title(title)
    dialogWindow.set_default_response(Gtk.ResponseType.OK)

    dialogBox = dialogWindow.get_content_area()
    text = ''

    if multiline:
        # Function to mark first line as bold
        def mark_heading(textbuff, tag):
            start = textbuff.get_start_iter()
            end = textbuff.get_end_iter()
            textbuff.remove_all_tags(start, end)
            match = start.forward_search('\n', 0, end)
            if match != None:
                match_start, match_end = match
                textbuff.apply_tag(tag, start, match_start)

        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_hexpand(True)
        scrolledwindow.set_vexpand(True)
        scrolledwindow.set_size_request(300, 100)

        textview = Gtk.TextView()
        textbuffer = textview.get_buffer()
        dialogBox.pack_end(scrolledwindow, False, False, 0)
        scrolledwindow.add(textview)
        scrolledwindow.set_border_width(6)

        # Set old value
        if oldval != None:
            textbuffer.set_text(oldval)

        # Mark heading
        tag_bold = textbuffer.create_tag("bold", weight=Pango.Weight.BOLD)
        mark_heading(textbuffer, tag_bold)
        textbuffer.connect("changed", mark_heading, tag_bold)

        dialogWindow.show_all()
        response = dialogWindow.run()
        text = textbuffer.get_text(textbuffer.get_start_iter(),textbuffer.get_end_iter(), True)
    else:
        userEntry = Gtk.Entry()
        userEntry.set_activates_default(True)
        userEntry.set_size_request(50, 0)
        dialogBox.pack_end(userEntry, False, False, 0)

        # Set old value
        if oldval != None:
            userEntry.set_text(oldval)

        dialogWindow.show_all()
        response = dialogWindow.run()
        text = userEntry.get_text()
    dialogWindow.destroy()
    if (response == Gtk.ResponseType.OK) and (text != ''):
        return text
    else:
        return None


