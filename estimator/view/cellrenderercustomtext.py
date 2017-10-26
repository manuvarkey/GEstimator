#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  cellrenderercustomtext.py
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


import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject, Pango

class CellRendererCustomText(Gtk.CellRendererText):

    full_text = GObject.Property(type=str)

    def __init__(self):
        Gtk.CellRendererText.__init__(self)
 
    def on_key_press_event(self, widget, event, raised_widget, editor, path):
        '''Catch pressing Enter keys and Tab.

        Shift, Ctrl or Alt combined with Return or Keypad Enter can be used
        for linebreaking. Pressing Return or Keypad Enter alone will finish
        editing.'''

        mask = event.get_state()
        keyname = Gdk.keyval_name(event.get_keyval()[1])
        
        accel_masks = (Gdk.ModifierType.CONTROL_MASK | \
                       Gdk.ModifierType.SHIFT_MASK | \
                       Gdk.ModifierType.MOD1_MASK)
        enter_keynames = ('Return', 'KP_Enter')
        tab_keynames = ('Tab', 'ISO_Left_Tab')

        if ((keyname in enter_keynames) and not (mask & accel_masks)) or (keyname in tab_keynames):
            buffer = editor.get_buffer()
            [start, end] = buffer.get_bounds()
            text = buffer.get_text(start,end,False)
            raised_widget.destroy()
            self.emit('edited', path, text)
        
    def do_activate(self, event, widget, path, background_area, cell_area, flags):
        
        popover =  Gtk.Popover.new(widget)
        popover.set_pointing_to(cell_area)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.props.width_request = background_area.width + 20
        popover.props.height_request = background_area.height + 50 if background_area.height < 300 else 300

        editor = Gtk.TextView()
        editor.set_wrap_mode(Gtk.WrapMode.WORD)
        editor.connect('key-press-event', self.on_key_press_event, popover, editor, path)
        editor.get_buffer().set_text(self.props.full_text)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_margin_top(6)
        scrolled.set_margin_bottom(6)
        scrolled.set_margin_left(6)
        scrolled.set_margin_right(6)
        scrolled.add(editor)
        popover.add(scrolled)

        popover.show_all()
        editor.grab_focus()

        return True
        
