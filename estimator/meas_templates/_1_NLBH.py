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
        def callback_total_item(values,row=None):
            # Evaluate data values
            data_str = values[2:6]
            data = []
            for x in data_str:
                try:
                    num = eval(x)
                    data.append(num)
                except:
                    data.append(0)
            # Evaluate product of non-zero values
            nonzero = [x for x in data if x!= 0]
            total = 1
            for x in nonzero:
                total *= x
            if len(nonzero) == 0:
                return '0'
            else:
                return str(round(total,3))

        def callback_breakup(values,row=None):
            data_str = values[2:6]
            breakup = "["
            for x in data_str:
                if x != "" and x!= '0':
                    breakup = breakup + str(x) + ","
                else:
                    breakup = breakup + ','
            breakup = breakup[:-1] + "]"
            return breakup

        def total_func(item_list,userdata=None):
            total = [0]
            for item in item_list:
                if item is not None:
                    total[0] += item.find_total()[0]
            total[0] = round(total[0],3)
            return total

        def total_func_item(values):
            # Evaluate product of non-zero values
            data = values[2:6]
            nonzero = [x for x in data if x!= 0]
            total = 1
            for x in nonzero:
                total *= x
            if len(nonzero) == 0:
                return [0]
            else:
                return [round(total,3)]

        # Define your variables here
        self.name = 'Item NLBH'
        self.itemnos_mask = [None]
        self.itemnos_mapping = [None]
        self.captions = ['Description', 'Breakup','No','L','B','H','Total']
        self.columntypes = [MEAS_DESC,MEAS_CUST,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_CUST]
        self.captions_udata = []
        self.columntypes_udata = []
        self.user_data_default = []
        # Define functions here
        self.cust_funcs = [None, callback_breakup, None, None, None, None, callback_total_item]
        self.total_func = total_func
        self.total_func_item = total_func_item
        self.dimensions = [[200,150,80,80,80,80,100], [True,False,False,False,False,False,False]]
