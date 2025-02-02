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

        # Custom call backs for columns

        def c_def(values,row=None):
            try:
                if values[0].find('Qty B/F') != -1:
                    l = ''
                else:
                    l = ''
                    for value in values[3:9]:
                        if value not in ['','0','0.0']:
                            l += str(eval(value)) + ','
                    l = l[:-1]
            except:
                l = ''
            return str(l)

        def c_1(values,row=None):
            try:
                n1 = eval(values[1])
                n2 = eval(values[2])
                l = eval(values[3])
                total = round(n1*n2*l,2)
            except:
                total = 0
            return str(total)

        def c_2(values,row=None):
            try:
                n1 = eval(values[1])
                n2 = eval(values[2])
                l = eval(values[4])
                total = round(n1*n2*l,2)
            except:
                total = 0
            return str(total)

        def c_3(values,row=None):
            try:
                n1 = eval(values[1])
                n2 = eval(values[2])
                l = eval(values[5])
                total = round(n1*n2*l,2)
            except:
                total = 0
            return str(total)

        def c_4(values,row=None):
            try:
                n1 = eval(values[1])
                n2 = eval(values[2])
                l = eval(values[6])
                total = round(n1*n2*l,2)
            except:
                total = 0
            return str(total)

        def c_5(values,row=None):
            try:
                n1 = eval(values[1])
                n2 = eval(values[2])
                l = eval(values[7])
                total = round(n1*n2*l,2)
            except:
                total = 0
            return str(total)

        def c_6(values,row=None):
            try:
                n1 = eval(values[1])
                n2 = eval(values[2])
                l = eval(values[8])
                total = round(n1*n2*l,2)
            except:
                total = 0
            return str(total)

        # Standard functions - modify as required

        def total_func(item_list,userdata):
            total = [0]*6
            for item in item_list:
                if item is not None:
                    sub_total = item.find_total()
                    for i,t in enumerate(sub_total):
                        total[i] += t
            grandtotal = 0
            for (i,t) in enumerate(total):
                try:
                    grandtotal += t*float(userdata[6+i])
                except:
                    pass
            return [round(grandtotal,3)]

        def total_func_item(values):
            # Populate data values
            n = values[1]*values[2]
            data_l = values[3:9]
            # Evaluate total
            total = [round(l*n,2) for l in data_l]
            return total

        def export_abstract(item_list,userdata):
            total = [0]*6
            for item in item_list:
                if item is not None:
                    sub_total = item.find_total()
                    for i,t in enumerate(sub_total):
                        total[i] += t
            total_str = [str(t) for t in total]
            return ['','1','1'] + total_str

        # Define your variables here
        self.name = 'Civil: Table of Steel Bars'
        self.itemnos_mask = [None]
        self.itemnos_mapping = [None]

        self.captions = ['Description','N1','N2','L1','L2','L3','L4','L5','L6','L',
                         'T1','T2','T3','T4','T5','T6']
        self.columntypes = [MEAS_DESC,MEAS_NO,MEAS_NO,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_CUST,
                            MEAS_CUST,MEAS_CUST,MEAS_CUST,MEAS_CUST,MEAS_CUST,MEAS_CUST]

        self.captions_udata = ['Item 1 Label','Item 2 Label','Item 3 Label','Item 4 Label','Item 5 Label','Item 6 Label',
                                'Item 1 constant','Item 2 constant','Item 3 constant','Item 4 constant','Item 5 constant','Item 6 constant']
        self.columntypes_udata = [MEAS_DESC,MEAS_DESC,MEAS_DESC,MEAS_DESC,MEAS_DESC,MEAS_DESC,
                                MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L,MEAS_L]
        self.user_data_default = ['8mm','10mm','12mm','16mm','20mm','25mm',
                                  '0.395','0.616','0.888','1.579','2.467','3.855']

        # Define functions here
        self.cust_funcs = [None, None, None, None, None, None, None, None, None, c_def,c_1,c_2,c_3,c_4,c_5,c_6]
        self.total_func = total_func
        self.total_func_item = total_func_item
        self.dimensions = [[200,40,40,50,50,50,50,50,50,100,50,50,50,50,50,50], [True,False,False,False,False,False,False,False,False,False,False,False,False,False,False,False]]
