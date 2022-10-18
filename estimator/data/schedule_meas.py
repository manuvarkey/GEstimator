#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# data.py
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

import logging

# Local module import
from .. import misc

# Get logger object
log = logging.getLogger()


# class storing individual items in schedule of work
class ScheduleItemGeneric:
    """Class stores a row in the generic schedule"""
    
    def __init__(self, item=None):
        if item is not None:
            self.item = item
        else:
            self.item = []

    def set_model(self, item):
        """Set data model"""
        self.item = item

    def get_model(self):
        """Get data model"""
        return self.item

    def __setitem__(self, index, value):
        self.item[index] = value

    def __getitem__(self, index):
        return self.item[index]

    def print_item(self):
        print(self.item)
        

class ScheduleGeneric:
    """Class stores a generic schedule"""
    
    def __init__(self, items=None):
        if items is not None:
            self.items = items  # main data store of rows
        else:
            self.items = []

    def append_item(self, item):
        """Append item at end of schedule"""
        self.items.append(item)

    def get_item_by_index(self, index):
        return self.items[index]

    def set_item_at_index(self, index, item):
        self.items[index] = item

    def insert_item_at_index(self, index, item):
        self.items.insert(index, item)

    def remove_item_at_index(self, index):
        del (self.items[index])

    def __setitem__(self, index, value):
        self.items[index] = value

    def __getitem__(self, index):
        return self.items[index]
    
    def get_model(self):
        """Get data model"""
        items = []
        for item in self.items:
            items.append(item.get_model())
        return items
        
    def set_model(self,items):
        """Set data model"""
        for item in items:
            self.items.append(ScheduleItemGeneric(item))
            
    def length(self):
        """Return number of rows"""
        return len(self.items)

    def clear(self):
        del self.items[:]

    def print_item(self):
        print("schedule start")
        for item in self.items:
            item.print_item()
        print("schedule end")
        
