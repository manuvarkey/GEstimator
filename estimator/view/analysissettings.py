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

# Setup logger object
log = logging.getLogger(__name__)

def get_analysis_settings(parent):

    builder = Gtk.Builder()
    builder.add_from_file(misc.abs_path("interface", "analysisimportsettings.glade"))
    dialog = builder.get_object("ana_settings_dialog")
    dialog.set_transient_for(parent)
    dialog.set_modal(True)
    
    # Get objects
    combo_comment = builder.get_object('combo_comment')
    combo_round = builder.get_object('combo_round')
    liststore_combo_comment = builder.get_object('liststore_combo_comment')
    liststore_combo_round = builder.get_object('liststore_combo_round')
    
    # Set default values
    combo_comment.set_active(1)
    combo_round.set_active(0)
    
    # Show settings dialog
    response = dialog.run()
    
    if response == 1:
        # Get values
        comment_loc_iter = combo_comment.get_active_iter()
        round_val_iter = combo_round.get_active_iter()
        comment_loc = liststore_combo_comment[comment_loc_iter][2]
        round_val = liststore_combo_round[round_val_iter][2]
        
        dialog.destroy()
        return (comment_loc, round_val)
    else:
        dialog.destroy()
        return None
      