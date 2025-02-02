#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# tableofpoints.py
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

# Item codes for schedule dialog * DONT CHANGE *
MEAS_NO = 1
MEAS_L = 2
MEAS_DESC = 3
MEAS_CUST = 4


class CustomItem:
    def __init__(self):

        def total_func(item_list,userdata=None):
            total = [0,0,0,0,0,0,0,0]
            for item in item_list:
                if item is not None:
                    itemtot = item.find_total()
                    for i in range(8):
                        total[i] += itemtot[i]
            for i in range(8):
                total[i] = round(total[i],3)
            return total

        def total_func_item(values):
            return [round(x,3) for x in values[1:9]]


        # Define your variables here
        self.name = 'Item NNNNNNNN'
        self.itemnos_mask = [None,None,None,None,None,None,None,None]
        self.itemnos_mapping = [1,2,3,4,5,6,7,8]
        self.captions = ['Description','N1','N2','N3','N4','N5','N6','N7','N8']
        self.columntypes = [MEAS_DESC,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L]
        self.captions_udata = []
        self.columntypes_udata = []
        self.user_data_default = []
        # Define functions here
        self.cust_funcs = [None, None, None, None, None, None, None, None, None]
        self.total_func = total_func
        self.total_func_item = total_func_item
        self.dimensions = [[200,80,80,80,80,80,80,80,80], [True,False,False,False,False,False,False,False,False]]
