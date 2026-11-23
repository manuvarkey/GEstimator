#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# misc.py
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

import copy
import json
import logging
import math
import os
import pathlib
import platform
import posixpath
import re
import subprocess
import threading
import time
from urllib.parse import urlparse
from urllib.request import url2pathname

import openpyxl
from prettytable import PrettyTable, TableStyle

from .arithmetic import evaluate_number

# Setup logger object
log = logging.getLogger(__name__)

## GLOBAL CONSTANTS

# Program name
PROGRAM_NAME = "GEstimator"
PROGRAM_AUTHOR = "CPWD"
PROGRAM_VER = "1"
# CMB error codes used for displaying info in main window
ERROR = -1
WARNING = -2
OK = 0
INFO = 0
# background colors for treeview
MEAS_COLOR_LOCKED = "#FFCC32"
MEAS_COLOR_LOCKED_L1 = "#FF9800"
MEAS_COLOR_LOCKED_L2 = "#B76D54"
MEAS_COLOR_MISSING = "#F44336"
MEAS_COLOR_NORMAL = None
MEAS_COLOR_SELECTED = "#3465a4"
MEAS_COLOR_HIGHLIGHTED = "#49b06e"

# Item codes for schedule dialog
MEAS_NO = 1
MEAS_L = 2
MEAS_DESC = 3
MEAS_CUST = 4

# String used for checking file version
PROJECT_FILE_VER = "GESTIMATOR_FILE_REFERENCE_VER_2"
PROJECT_EXTENSION = ".eproj"

# Sub Analysis item
SUB_ANA_TITLE = "SUB ANALYSIS"
SUB_ANA_SEARCH_DEPTH = 2

# Limiting values
MAX_DESC_LEN = 1000
MAX_DESC_LEN_MEAS = 100

ana_copy_add_items = []
ana_default_add_items = [
    {"description": "MATERIALS", "code": "", "itemtype": 0, "resource_list": []},
    {"description": "Add Cartage @ 1%", "value": 0.01, "itemtype": 2},
    {"description": "LABOUR", "code": "", "itemtype": 0, "resource_list": []},
    {"description": "TOTAL", "itemtype": 1},
    {"description": "Add CP&OH @ 15%", "value": 0.15, "itemtype": 2},
    {"description": "TOTAL", "itemtype": 1},
    {"description": "Add LC @ 1%", "value": 0.01, "itemtype": 2},
    {"description": "TOTAL", "itemtype": 1},
    {"description": "Add 18% GST", "value": 0.18, "itemtype": 2},
    {"description": "TOTAL", "itemtype": 1},
    {"description": "Say", "value": 0, "itemtype": 4},
]


# Default project settings
default_project_settings = {
    "file_version": PROJECT_FILE_VER,
    "project_name": "",
    "project_item_code": "",
    "project_resource_code": "",
    "project_measurement": '["Measurement", ["", []]]',
}
default_program_settings = {
    "export_break_items": "True",
    "sch_rate_mult_factor": "1",
    "ana_copy_delete_rows": "0",
    "ana_copy_add_items": ana_copy_add_items,
    "ana_default_add_items": ana_default_add_items,
}
# Item codes for project global variables
global_vars = [
    "$cmbnameofwork$",
    "$cmbagency$",
    "$cmbagmntno$",
    "$cmbsituation$",
    "$cmbdateofstart$",
    "$cmbdateofstartasperagmnt$",
    "$cmbissuedto$",
    "$cmbvarifyingauthority$",
    "$cmbvarifyingauthorityoffice$",
    "$cmbissuingauthority$",
    "$cmbissuingauthorityoffice$",
]
global_vars_captions = [
    "Name of Work",
    "Agency",
    "Agreement Number",
    "Situation",
    "Date of Start",
    "Date of start as per Agmnt.",
    "CMB Issued to",
    "Varifying Authority",
    "Varifying Authority Office",
    "Issuing Authority",
    "Issuing Authority Office",
]


## GLOBAL VARIABLES


## GLOBAL CLASSES


class Spreadsheet:
    """Manage input and output of spreadsheets"""

    def __init__(self, filename=None):
        if filename is not None:
            self.spreadsheet = openpyxl.load_workbook(filename)
        else:
            self.spreadsheet = openpyxl.Workbook()
        self.sheet = self.spreadsheet.active

    def save(self, filename):
        """Save worksheet to file"""
        self.spreadsheet.save(filename)

    # Sheet management

    def new_sheet(self):
        """Create a new sheet to spreadsheet and set as active"""
        self.sheet = self.spreadsheet.create_sheet()

    def sheets(self):
        """Returns a list of sheetnames"""
        return self.spreadsheet.sheetnames

    def length(self):
        """Get number of rows in sheet"""
        # Worksheet.max_row scans every cell; exports call length() per row,
        # which made large exports quadratic. Track the extent while writing.
        rows = getattr(self.sheet, "_gestimator_rows", None)
        if rows is None:
            rows = self.sheet.max_row
            self.sheet._gestimator_rows = rows
        return rows

    def _touch(self, row):
        """Record that cells up to row exist (see length)."""
        if row > self.length():
            self.sheet._gestimator_rows = row

    def set_title(self, title):
        """Set title of sheet"""
        self.sheet.title = title

    def set_page_settings(self, orientation="portrait", papersize="A4", font=None, print_title_rows=None):
        # Orientation
        if orientation == "portrait":
            self.sheet.page_setup.orientation = openpyxl.worksheet.worksheet.Worksheet.ORIENTATION_PORTRAIT
        elif orientation == "landscape":
            self.sheet.page_setup.orientation = openpyxl.worksheet.worksheet.Worksheet.ORIENTATION_LANDSCAPE

        # Paper size
        if papersize == "A4":
            self.sheet.page_setup.paperSize = openpyxl.worksheet.worksheet.Worksheet.PAPERSIZE_A4

        # Print title rows
        self.sheet.print_title_rows = print_title_rows

        # General settings
        self.sheet.page_setup.fitToPage = True
        self.sheet.page_setup.fitToHeight = 99
        self.sheet.page_setup.fitToWidth = 1
        self.sheet.print_options.horizontalCentered = True

        # Set font
        if font:
            # sheet[row] recomputes the sheet width on every call (quadratic for
            # large sheets); iterate once and reuse one font per distinct style.
            fonts = {}
            width = self.sheet.max_column
            for row in self.sheet.iter_rows(min_row=1, max_row=self.length(), max_col=width):
                for cell in row:
                    if isinstance(cell, openpyxl.cell.cell.MergedCell):
                        continue
                    key = cell._style.fontId if getattr(cell, "_style", None) is not None else 0
                    if key not in fonts:
                        font_style = copy.copy(cell.font)
                        font_style.name = font
                        fonts[key] = font_style
                    cell.font = fonts[key]

    def set_column_widths(self, widths):
        """Set column widths of sheet"""
        for column, width in enumerate(widths, 1):
            col_letter = openpyxl.utils.get_column_letter(column)
            self.sheet.column_dimensions[col_letter].width = width

    def set_active_sheet(self, sheetref):
        """Set active sheet of spreadsheet"""
        sheetname = ""
        sheetno = None
        if type(sheetref) is int:
            sheetno = sheetref
        elif type(sheetref) is str:
            sheetname = sheetref

        if sheetname in self.sheets():
            self.sheet = self.spreadsheet[sheetname]
        elif sheetno is not None and sheetno < len(self.sheets()):
            self.sheet = self.spreadsheet[self.sheets()[sheetno]]

    def set_style(self, row, col, bold=False, wrap_text=True, horizontal="general", vertical="bottom", fill=None):
        """Set style of individual cell"""
        font = openpyxl.styles.Font(bold=bold)
        alignment = openpyxl.styles.Alignment(wrap_text=wrap_text, horizontal=horizontal, vertical=vertical)

        self._touch(row)
        self.sheet.cell(row=row, column=col).font = font
        self.sheet.cell(row=row, column=col).alignment = alignment

        if fill == "#FFFFFF":
            patternfill = openpyxl.styles.PatternFill()
            self.sheet.cell(row=row, column=col).fill = patternfill
        elif fill is not None:
            patternfill = openpyxl.styles.PatternFill(start_color=fill[1:], end_color=fill[1:], fill_type="solid")
            self.sheet.cell(row=row, column=col).fill = patternfill

    # Data addition functions

    def append(self, ss_obj):
        """Append an sheet to current sheet"""
        sheet = ss_obj.spreadsheet.active
        rowcount = self.length()
        for row_no, row in enumerate(sheet.rows, 1):
            self._touch(row_no + rowcount)
            for col_no, cell in enumerate(row, 1):
                self.sheet.cell(row=row_no + rowcount, column=col_no).value = cell.value
                if cell.has_style:
                    self.sheet.cell(row=row_no + rowcount, column=col_no).font = copy.copy(cell.font)
                    self.sheet.cell(row=row_no + rowcount, column=col_no).border = copy.copy(cell.border)
                    self.sheet.cell(row=row_no + rowcount, column=col_no).fill = copy.copy(cell.fill)
                    self.sheet.cell(row=row_no + rowcount, column=col_no).number_format = copy.copy(cell.number_format)
                    self.sheet.cell(row=row_no + rowcount, column=col_no).protection = copy.copy(cell.protection)
                    self.sheet.cell(row=row_no + rowcount, column=col_no).alignment = copy.copy(cell.alignment)

    def append_data(
        self, data, bold=False, italic=False, wrap_text=True, horizontal="general", vertical="bottom", fill=None
    ):
        """Append data to current sheet"""
        rowcount = self.length()
        self.insert_data(data, rowcount + 1, 1, bold, italic, wrap_text, horizontal, vertical, fill)

    def insert_data(
        self,
        data,
        start_row=1,
        start_col=1,
        bold=False,
        italic=False,
        wrap_text=True,
        horizontal="general",
        vertical="bottom",
        fill=None,
    ):
        """Insert data to current sheet"""
        # Setup styles
        font = openpyxl.styles.Font(bold=bold, italic=italic)

        if fill == "#FFFFFF":
            patternfill = openpyxl.styles.PatternFill()
        elif fill is not None:
            patternfill = openpyxl.styles.PatternFill(start_color=fill[1:], end_color=fill[1:], fill_type="solid")

        alignment = openpyxl.styles.Alignment(wrap_text=wrap_text, horizontal=horizontal, vertical=vertical)
        # Apply data and styles
        for row_no, row in enumerate(data, start_row):
            self._touch(row_no)
            for col_no, value in enumerate(row, start_col):
                self.sheet.cell(row=row_no, column=col_no).value = value
                self.sheet.cell(row=row_no, column=col_no).font = font

                if fill:
                    self.sheet.cell(row=row_no, column=col_no).fill = patternfill

                self.sheet.cell(row=row_no, column=col_no).alignment = alignment

    def add_merged_cell(
        self, value, row=None, width=2, bold=False, wrap_text=True, horizontal="center", start_column=1
    ):
        """Add a merged cell of prescrbed width"""
        if row is None:
            rowstart = self.length() + 1
        else:
            rowstart = row
        if row is None:
            # A freshly appended row cannot overlap an existing merge; skip
            # openpyxl's linear overlap scan (quadratic over large exports).
            from openpyxl.utils import get_column_letter
            from openpyxl.worksheet.merge import MergedCellRange

            coord = "{0}{1}:{2}{1}".format(
                get_column_letter(start_column), rowstart, get_column_letter(start_column + width - 1)
            )
            merged = MergedCellRange(self.sheet, coord)
            self.sheet.merged_cells.ranges.add(merged)
            self.sheet._clean_merge_range(merged)
        else:
            self.sheet.merge_cells(
                start_row=rowstart, start_column=start_column, end_row=rowstart, end_column=start_column + width - 1
            )
        self._touch(rowstart)
        self.__setitem__([rowstart, start_column], value)
        self.set_style(rowstart, start_column, bold, wrap_text, horizontal)

    def __setitem__(self, index, value):
        """Set an individual cell"""
        self._touch(index[0])
        self.sheet.cell(row=index[0], column=index[1]).value = value

    def __getitem__(self, index):
        """Set an individual cell"""
        self._touch(index[0])
        return self.sheet.cell(row=index[0], column=index[1]).value

    # Bulk read functions

    def read_rows(self, columntypes=[], start=0, end=-1, left=0, allow_formula=False):
        """Read and validate selected rows from current sheet"""
        # Get count of rows
        rowcount = self.length()
        if end < 0 or end >= rowcount:
            count_actual = rowcount
        else:
            count_actual = end

        items = []
        for row in range(start, count_actual):
            cells = []
            skip = 0  # No of columns to be skiped ex. breakup, total etc...
            for columntype, i in zip(columntypes, list(range(left, len(columntypes) + left))):
                cell = self.sheet.cell(row=row + 1, column=i - skip + 1).value
                if columntype == str:
                    if cell is None:
                        cell_formated = ""
                    else:
                        cell_formated = str(cell)
                elif columntype == float:
                    if cell is None:
                        if allow_formula:
                            cell_formated = "0"
                        else:
                            cell_formated = 0
                    else:
                        if allow_formula:
                            try:  # try evaluating float
                                if len(str(cell)) > 1 and str(cell)[0] == "=":
                                    formula = str(cell)[1:]
                                else:
                                    formula = str(cell)
                                evaluated = str(float(evaluate_number(formula)))
                                cell_formated = formula
                            except:
                                cell_formated = "0"
                        else:
                            try:  # try evaluating float
                                cell_formated = str(float(cell))
                            except:
                                cell_formated = 0

                elif columntype == int:
                    if cell is None:
                        if allow_formula:
                            cell_formated = "0"
                        else:
                            cell_formated = 0
                    else:
                        if allow_formula:
                            try:  # try evaluating int
                                if len(str(cell)) > 1 and str(cell)[0] == "=":
                                    formula = str(cell)[1:]
                                else:
                                    formula = str(cell)
                                evaluated = str(int(evaluate_number(formula)))
                                cell_formated = formula
                            except:
                                cell_formated = "0"
                        else:
                            try:  # try evaluating int
                                cell_formated = str(int(cell))
                            except:
                                cell_formated = 0
                else:
                    cell_formated = ""
                    log.warning("Spreadsheet - Value skipped on import - " + str((row, i)))
                if columntype is None:
                    skip = skip + 1
                cells.append(cell_formated)
            items.append(cells)
        return items


class Command(object):
    """Runs a command in a seperate thread"""

    def __init__(self, cmd):
        """Initialises class with command to be executed"""
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        """Run set command with selected timeout"""

        def target():
            if platform.system() == "Linux":
                self.process = subprocess.Popen(self.cmd)
            elif platform.system() == "Windows":
                self.process = subprocess.Popen(self.cmd, shell=True)
            log.info("Sub-process spawned - " + str(self.process.pid))
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            log.error("Terminating sub-process exceeding timeout - " + str(self.process.pid))
            self.process.terminate()
            thread.join()
            return -1
        return 0


## GLOBAL METHODS


def file_to_uri(filename):
    if platform.system() == "Windows":
        path = pathlib.PureWindowsPath(filename)
        uri = path.as_uri()
        # If network path
        if filename.startswith(r"\\"):
            uri = uri[0:7] + "//" + uri[7:]
    else:
        path = pathlib.Path(filename)
        uri = path.as_uri()
    return uri


def uri_to_file(uri):
    return url2pathname(urlparse(uri).path)


def abs_path(*args):
    """Returns absolute path to the relative path provided"""
    return os.path.join(os.path.split(__file__)[0], *args)


def dir_from_path(path):
    """Returns directory path from file path"""
    return os.path.dirname(path)


def posix_path(*args):
    """Returns platform independent filename"""
    if platform.system() == "Windows":
        if len(args) > 1:
            path = os.path.normpath(posixpath.join(*args))
        else:
            path = os.path.normpath(args[0])
        # remove any leading slash
        if path[0] == "\\":
            return path[1:]
        else:
            return path
    else:
        if len(args) > 1:
            return posixpath.join(*args)
        else:
            return args[0]


def open_file(filename, abs=True):
    if abs:
        filename_mod = abs_path(filename)
    else:
        filename_mod = filename

    if platform.system() == "Linux":
        subprocess.call(("xdg-open", filename_mod))
    elif platform.system() == "Windows":
        os.startfile(filename_mod)


def get_file_path_from_dnd_dropped_uri(uri):
    # Get the path to file
    path = ""
    if uri.startswith("file:\\\\\\"):  # windows
        path = uri[8:]  # 8 is len('file:///')
    elif uri.startswith("file://"):  # nautilus, rox
        path = uri[7:]  # 7 is len('file://')
    elif uri.startswith("file:"):  # xffm
        path = uri[5:]  # 5 is len('file:')

    path = url2pathname(path)  # escape special chars
    path = path.strip("\r\n\x00")  # remove \r\n and NULL

    return path


def human_code(code):
    """Returns a weighted value for sorting codes"""

    def tryint(s):
        # For integer
        try:
            return int(s)
        # For string
        except ValueError:
            return s

    ret_list = []

    for c in re.split("([0-9]+)", code):
        ret = tryint(c)
        if ret not in ["", " "]:
            ret_list.append(ret)

    return ret_list


def remove_markup(text):
    """Clear markup text of special characters"""
    return re.sub("<[^<]+?>", "", text)


def clean_markup(text):
    """Clear markup text of special characters"""
    for splchar, replspelchar in zip(["&", "<", ">"], ["&amp;", "&lt;", "&gt;"]):
        text = text.replace(splchar, replspelchar)
    return text


def get_ellipsized_text(text, length, singleline=False):
    if len(text) > length:
        if singleline:
            desc = text[0 : (int(length / 2) - 3)] + " ... " + text[-(int(length / 2) - 3) :]
        else:
            desc = text[0 : (int(length / 2) - 3)] + "\n ... \n" + text[-(int(length / 2) - 3) :]
    else:
        desc = text
    return desc


def get_tabular_text(data, col_labels=None):
    table = PrettyTable()
    table.set_style(TableStyle.PLAIN_COLUMNS)
    table.align = "l"
    if col_labels:
        table.field_names = col_labels
    else:
        table.header = False
    table.add_rows(data)
    return table.get_string()


def round_value(value, rounding="Round to 0"):
    """Round value using predefined schemes"""
    if rounding == "Round within 1%":
        rounded = round(value, -int(round(math.log10(value * 0.01), 0)))
    elif rounding == "Round within 5%":
        rounded = round(value, -int(round(math.log10(value * 0.05), 0)))
    elif rounding == "Round within 10%":
        rounded = round(value, -int(round(math.log10(value * 0.1), 0)))
    elif rounding == "Round to 10000":
        rounded = round(value, -4)
    elif rounding == "Round to 1000":
        rounded = round(value, -3)
    elif rounding == "Round to 100":
        rounded = round(value, -2)
    elif rounding == "Round to 10":
        rounded = round(value, -1)
    elif rounding == "Round to 0":
        rounded = round(value, 0)
    elif rounding == "Round to .0":
        rounded = round(value, 1)
    elif rounding == "Round to .00":
        rounded = round(value, 2)
    elif rounding == "Round to .000":
        rounded = round(value, 3)
    else:
        rounded = value
    return rounded


# Cairo drawing functions


def rgb2hex(r, g, b, a=None):
    if a:
        return "#{:02x}{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255), int(a * 255))
    else:
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def hex2rgb(hexcode):
    if len(hexcode) == 7:
        r = int(hexcode[1:3], 16) / 255
        g = int(hexcode[3:5], 16) / 255
        b = int(hexcode[5:7], 16) / 255
        a = 1
    elif len(hexcode) == 9:
        r = int(hexcode[1:3], 16) / 255
        g = int(hexcode[3:5], 16) / 255
        b = int(hexcode[5:7], 16) / 255
        a = int(hexcode[7:9], 16) / 255
    return (r, g, b, a)
