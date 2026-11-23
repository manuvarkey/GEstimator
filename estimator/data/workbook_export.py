#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# workbook_export.py
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

"""Workbook writers shared by the schedule database's export entry points."""

import logging
from decimal import Decimal

log = logging.getLogger()


def write_schedule(database, spreadsheet, break_lines=False):
    """Write schedule rows and subtotal formulas."""
    sch_table = database.get_item_table()
    proj_name = database.get_project_settings()["project_name"]

    # Header
    spreadsheet.add_merged_cell("SCHEDULE OF RATES", width=7, bold=True)
    rows = [[None]]
    spreadsheet.append_data(rows)
    spreadsheet.add_merged_cell("Name of Work: " + proj_name, width=6, start_column=2, bold=True, horizontal="left")
    rows = [[None], ["Sl.No.", "Description", "Unit", "Rate", "Qty", "Amount", "Remarks"], [None]]
    spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal="center")
    s_row = 8

    # Insert data
    for category, items in sch_table.items():
        # Add category item
        rows = [[None, category]]
        spreadsheet.append_data(rows, bold=True)
        s_row = s_row + 1
        # Set data of 1st level items
        for code, item_list in items.items():
            item = item_list[0]
            item_desc = item[1]
            item_unit = item[2]
            item_colour = item[6]

            if break_lines:
                # If item has multiple lines split up lines
                item_desc_parts = item_desc.split("\n")
                if len(item_desc_parts) > 1:
                    for part in item_desc_parts[0:-1]:
                        item_row = [code, part, None, None, None, None, None]
                        code = None
                        spreadsheet.append_data([item_row], fill=item_colour)
                        spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                        s_row = s_row + 1
                    item_desc = item_desc_parts[-1]

            if item_unit == "":
                item_rate = None
                item_qty = None
                item_amount = None
            else:
                item_rate = item[3]
                item_qty = item[4]
                item_amount = "=ROUND(D" + str(s_row) + "*E" + str(s_row) + ",2)"
            item_remarks = item[5]

            item_row = [code, item_desc, item_unit, item_rate, item_qty, item_amount, item_remarks]
            spreadsheet.append_data([item_row], fill=item_colour)
            spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
            s_row = s_row + 1
            # Set data of 2nd level items
            for sub_item in item_list[1]:
                code = sub_item[0]
                desc = sub_item[1]
                unit = sub_item[2]
                rate = sub_item[3]
                qty = sub_item[4]
                remarks = sub_item[5]
                colour = sub_item[6]

                if break_lines:
                    # If item has multiple lines split up lines
                    item_desc_parts = desc.split("\n")
                    if len(item_desc_parts) > 1:
                        for part in item_desc_parts[0:-1]:
                            item_row = [code, part, None, None, None, None, None]
                            code = None
                            spreadsheet.append_data([item_row], fill=colour)
                            spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                            s_row = s_row + 1
                        desc = item_desc_parts[-1]

                amount = "=ROUND(D" + str(s_row) + "*E" + str(s_row) + ",2)"

                row = [code, desc, unit, rate, qty, amount, remarks]
                spreadsheet.append_data([row], fill=colour)
                spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                s_row = s_row + 1
    # Add sum of amount
    amount = "=ROUND(SUM(F7:F" + str(s_row) + "),2)"
    rows = [[None], [None, "TOTAL", None, None, None, amount]]
    spreadsheet.append_data(rows, bold=True)

    # General formating
    spreadsheet.set_title("Schedule")
    spreadsheet.set_column_widths([10, 50, 10, 10, 10, 15, 15])
    spreadsheet.set_page_settings(font="Consolas", print_title_rows="6:7")
    log.info("ScheduleDatabase - export_sch_spreadsheet - Schedule exported")


def write_resources(database, spreadsheet):
    """Write the resource catalog and its categories."""
    spreadsheet.new_sheet()
    spreadsheet.set_title("Resources")

    res_table = database.get_resource_table()

    # Header
    spreadsheet.add_merged_cell("SCHEDULE OF RESOURCES", width=8, bold=True)
    rows = [[None], ["Sl.No.", "Description", "Unit", "Rate", "Tax", "Discount", "Reference", "Category"], [None]]
    spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal="center")
    s_row = 6

    # Insert data
    for category, items in res_table.items():
        # Add category item
        rows = [[None, category]]
        spreadsheet.append_data(rows, bold=True)
        s_row = s_row + 1

        # Set data of resource items
        for code, item in items.items():
            item_row = item + [category]
            spreadsheet.append_data([item_row])
            spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
            s_row = s_row + 1

    # General formating
    spreadsheet.set_column_widths([10, 40, 10, 10, 10, 15, 25, 25])
    spreadsheet.set_page_settings(font="Consolas")
    log.info("ScheduleDatabase - export_res_spreadsheet - Schedule exported")


def write_analysis_item(database, code, spreadsheet, parent=None):
    """Append one item's analysis, keeping formula anchors in sheet order."""
    # ScheduleDatabase imports this writer, so load its row kinds here.
    from .schedule import ScheduleItemModel

    sch_item = database.get_item(code, modify_res_code=False)
    if sch_item.ana_items:
        s_row = spreadsheet.length() + 1

        # If parent item is there fill in code and decription
        if parent:
            [parent_code, item_desc] = parent
            spreadsheet.add_merged_cell(item_desc, width=5, start_column=2, horizontal="left")
            spreadsheet[s_row, 1] = parent_code
            spreadsheet.set_style(s_row, 1, horizontal="center", bold=True)
            s_row = s_row + 1

        # Add item number and description
        item_description = sch_item.description
        spreadsheet.add_merged_cell(item_description, width=5, start_column=2, horizontal="left")
        spreadsheet[s_row, 1] = code
        spreadsheet.set_style(s_row, 1, horizontal="center", bold=True)
        s_row = s_row + 1
        # Add item ana_remarks
        spreadsheet.add_merged_cell(sch_item.ana_remarks, width=5, start_column=2, horizontal="left")
        s_row = s_row + 1
        # Add header row
        header = [["Code", "Description", "Unit", "Qty", "Rate", "Amount"]]
        spreadsheet.append_data(header, bold=True, horizontal="center")
        s_row = s_row + 1

        sum_item = "0"
        sum_total = "0"
        for slno, item in enumerate(sch_item.ana_items):
            if item["itemtype"] == ScheduleItemModel.ANA_GROUP:
                # Add analysis group
                code = item["code"]
                description = item["description"]
                spreadsheet.append_data([[code, description]], bold=True)
                s_row_start = s_row
                s_row = s_row + 1
                # Add resources
                for resource_item in item["resource_list"]:
                    res_code = resource_item[0]
                    qty = resource_item[1]
                    remarks = resource_item[2]
                    resource = sch_item.resources[resource_item[0]]
                    res_description = resource.description
                    res_unit = resource.unit
                    rate = resource.rate
                    vat = resource.vat
                    discount = resource.discount
                    if vat or discount:
                        rate_formula = (
                            "=ROUND(" + str(rate) + "*" + str(1 + vat / 100) + "*" + str(1 - discount / 100) + ",2)"
                        )
                    else:
                        rate_formula = rate
                    amount = "=ROUND(D" + str(s_row) + "*E" + str(s_row) + ",2)"

                    rate_desc = "Basic rate " + str(rate)
                    ref_desc = " [" + resource.reference + "]" if resource.reference else ""
                    vat_desc = " + Tax @" + str(vat) + "%" if vat else ""
                    discount_desc = " - Discount @" + str(discount) + "%" if discount else ""
                    if vat or discount or ref_desc:
                        net_description = (
                            res_description + "\n(" + rate_desc + ref_desc + vat_desc + discount_desc + ")"
                        )
                    else:
                        net_description = res_description

                    row = [res_code, net_description, res_unit, qty, rate_formula, amount]
                    spreadsheet.append_data([row])
                    spreadsheet.set_style(s_row, 1, horizontal="center")
                    s_row = s_row + 1
                    if remarks:
                        spreadsheet.append_data([[None, " " + remarks]], italic=True)
                        s_row = s_row + 1
                total_desc = ("TOTAL of " + description) if code in [None, ""] else "TOTAL of " + code
                total_total = "=SUM(F" + str(s_row_start) + ":F" + str(s_row - 1) + ")"
                spreadsheet.append_data([[None, total_desc, None, None, None, total_total]])
                sum_item = "F" + str(s_row)
                sum_total = (sum_total + "+" + sum_item) if sum_total != "0" else sum_item
                s_row = s_row + 1

            elif item["itemtype"] == ScheduleItemModel.ANA_SUM:
                desc = item["description"]
                spreadsheet.append_data([[None, desc, None, None, None, "=" + sum_total]])
                sum_item = sum_total = "F" + str(s_row)
                s_row = s_row + 1

            elif item["itemtype"] == ScheduleItemModel.ANA_WEIGHT:
                desc = item["description"]
                value = item["value"]
                total = "=ROUND(" + str(value) + "*" + sum_item + ",2)"
                spreadsheet.append_data([[None, desc, None, None, None, total]])
                sum_total = sum_total + "+ F" + str(s_row)
                s_row = s_row + 1

            elif item["itemtype"] == ScheduleItemModel.ANA_TIMES:
                desc = item["description"]
                value = item["value"]
                total = "=ROUND(" + str(value) + "*" + sum_item + ",2)"
                spreadsheet.append_data([[None, desc, None, None, None, total]])
                sum_item = sum_total = "F" + str(s_row)
                s_row = s_row + 1

            elif item["itemtype"] == ScheduleItemModel.ANA_ROUND:
                desc = item["description"]
                value = item["value"]
                if int(value) == value:
                    total = "=ROUND(" + sum_total + "," + str(value) + ")"
                else:
                    precision = int(value)
                    base = int((value - int(value)) * 10)
                    total = "=MROUND(" + sum_total + "," + str(base * 10**-precision) + ")"
                spreadsheet.append_data([[None, desc, None, None, None, total]], bold=True)
                sum_item = sum_total = "F" + str(s_row)
                s_row = s_row + 1

        spreadsheet.append_data([[None], [None]])


def write_analysis(database, spreadsheet, progress, range_progress):
    """Write all analyses in schedule order and report item progress."""
    sch_table = database.get_item_table()
    spreadsheet.new_sheet()
    spreadsheet.set_title("Analysis")

    # Header
    spreadsheet.add_merged_cell("ANALYSIS OF RATES", width=6, bold=True)
    rows = [[None]]
    spreadsheet.append_data(rows)
    # Current row in spreadsheet
    s_row = 4
    # Total items for progress updation
    total_items = 0
    cur_item = 0
    for category in sch_table:
        total_items = total_items + len(sch_table[category])

    # Insert data
    for category, items in sch_table.items():
        # Add category item
        rows = [[None, category], [None]]
        spreadsheet.append_data(rows, bold=True)
        s_row = s_row + 2
        # Set data of 1st level items
        for code, item_list in items.items():
            item = item_list[0]
            item_desc = item[1]
            item_unit = item[2]
            # If parent item
            if item_unit == "":
                # Set data of 2nd level items
                for sub_item in item_list[1]:
                    code2 = sub_item[0]
                    database.export_ana_item_spreadsheet(code2, spreadsheet, [code, item_desc])
                    s_row = spreadsheet.length() + 1
            # If regular item
            else:
                database.export_ana_item_spreadsheet(code, spreadsheet)
                s_row = spreadsheet.length() + 1
            progress.set_fraction(range_progress[0] + (range_progress[1] - range_progress[0]) * cur_item / total_items)
            cur_item = cur_item + 1
        log.info("ScheduleDatabase - export_ana_spreadsheet - Analysis exported - " + category)

    spreadsheet.set_column_widths([10, 50, 10, 15, 10, 15])
    spreadsheet.set_page_settings(font="Consolas")
    log.info("ScheduleDatabase - export_ana_spreadsheet - Analysis exported")


def write_resource_usage(database, spreadsheet):
    """Write project resource totals using the engine's currency precision."""
    # Use the engine's currency function without a module import cycle.
    from .schedule import Currency

    cat_res_items = database.get_res_usage()
    spreadsheet.new_sheet()
    spreadsheet.set_title("Res Usage")

    # Header
    spreadsheet.add_merged_cell("WORK RESOURCE USAGE", width=6, bold=True)
    rows = [[None], ["Code", "Description", "Unit", "Rate", "Qty", "Amount"], [None]]
    spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal="center")
    s_row = 6

    for category, res_list_item in cat_res_items.items():
        # Add category item
        rows = [[None, category]]
        spreadsheet.append_data(rows, bold=True)
        s_row = s_row + 1
        for code, item in sorted(res_list_item.items()):
            description = item[1]
            unit = item[2]
            qty = item[3]
            basicrate = Currency(item[4])
            vat = Currency(item[5], 4) if item[5] is not None else Decimal(0)
            discount = Currency(item[6]) if item[6] is not None else Decimal(0)
            rate = Currency(basicrate * (1 + vat / 100) * (1 - discount / 100))
            amount_formula = "=ROUND(D" + str(s_row) + "*E" + str(s_row) + ",2)"
            rows = [[code, description, unit, rate, qty, amount_formula]]
            spreadsheet.append_data(rows)
            s_row = s_row + 1

    spreadsheet.set_column_widths([10, 50, 10, 10, 15, 15])
    spreadsheet.set_page_settings(font="Consolas")

    log.info("ScheduleDatabase - export_res_usage_spreadsheet - Resource Usage exported")


def write_measurements(database, spreadsheet, break_lines=False):
    """Write the measurement details and linked schedule abstract."""
    # Get measurement
    meas = database.get_measurement()
    sch_table = database.get_item_table()
    sch_table_flat = database.get_item_table(flat=True)
    (netpaths, netqtys, netsums) = meas.get_net_measurement()
    codes = dict()
    for key in netqtys:
        if key is not None:
            code = database.get_item_code(key)
            codes[key] = code

    spreadsheet.new_sheet()
    spreadsheet.set_title("DOM")

    # Header
    spreadsheet.add_merged_cell("DETAILS OF MEASUREMENTS", width=4, bold=True)
    rows = [[None]]
    spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal="center")
    s_row = 4

    measurement_sheet = meas.get_spreadsheet_buffer(sch_table_flat, codes, s_row)
    spreadsheet.append(measurement_sheet)
    s_row = s_row + measurement_sheet.length()

    # Insert abstract
    rows = [[None], [None]]
    spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal="center")
    spreadsheet.add_merged_cell("ABSTRACT OF MEASUREMENTS", width=4, bold=True)
    rows = [[None], ["Code", "Description", "Unit", "Qty"], [None]]
    spreadsheet.append_data(rows, bold=True, wrap_text=False, horizontal="center")
    s_row = s_row + 6

    for category, items in sch_table.items():
        # Add category item
        rows = [[None, category], [None]]
        spreadsheet.append_data(rows, bold=True)
        s_row = s_row + 2
        # Set data of 1st level items
        for code, item_list in items.items():
            item = item_list[0]
            item_desc = item[1]
            item_unit = item[2]
            item_qty = item[4]
            key = database.get_item_key(code)

            if break_lines:
                # If item has multiple lines split up lines
                item_desc_parts = item_desc.split("\n")
                if len(item_desc_parts) > 1:
                    for part in item_desc_parts[0:-1]:
                        item_row = [code, part, None, None]
                        code = None
                        spreadsheet.append_data([item_row])
                        spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                        s_row = s_row + 1
                    item_desc = item_desc_parts[-1]

            if item_unit == "":
                item_row = [code, item_desc, None, None]
                spreadsheet.append_data([item_row])
                spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                s_row = s_row + 1
            else:
                # Add detail from measurements
                if key in netqtys:
                    item_qty = item[4]
                    item_row = [code, item_desc, item_unit]
                    spreadsheet.append_data([item_row])
                    spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                    s_row = s_row + 1
                    s_row_start = s_row
                    for path, qty in zip(netpaths[key], netqtys[key]):
                        item_row = [None, "B/F MEASUREMENT # " + str(path + 1), item_unit, qty]
                        spreadsheet.append_data([item_row])
                        spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                        s_row = s_row + 1
                    # Sum of quantity
                    item_row = [None, "TOTAL", item_unit, "=SUM(D" + str(s_row_start) + ":D" + str(s_row - 1) + ")"]
                    spreadsheet.append_data([item_row, [None]])
                    spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                    s_row = s_row + 2
                # Add detail from schedule
                else:
                    item_row = [code, item_desc, item_unit, item_qty]
                    spreadsheet.append_data([item_row, [None]])
                    spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                    s_row = s_row + 2
            # Set data of 2nd level items
            for sub_item in item_list[1]:
                code = sub_item[0]
                desc = sub_item[1]
                unit = sub_item[2]
                qty = sub_item[4]
                key = database.get_item_key(code)

                if break_lines:
                    # If item has multiple lines split up lines
                    item_desc_parts = desc.split("\n")
                    if len(item_desc_parts) > 1:
                        for part in item_desc_parts[0:-1]:
                            item_row = [code, part, None, None]
                            code = None
                            spreadsheet.append_data([item_row])
                            spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                            s_row = s_row + 1
                        desc = item_desc_parts[-1]

                # Add detail from measurements
                if key in netqtys:
                    item_qty = item[4]
                    item_row = [code, desc, unit]
                    spreadsheet.append_data([item_row])
                    spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                    s_row = s_row + 1
                    s_row_start = s_row
                    for path, qty in zip(netpaths[key], netqtys[key]):
                        item_row = [None, "B/F MEASUREMENT # " + str(path + 1), unit, qty]
                        spreadsheet.append_data([item_row])
                        spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                        s_row = s_row + 1
                    # Sum of quantity
                    item_row = [None, "TOTAL", unit, "=SUM(D" + str(s_row_start) + ":D" + str(s_row - 1) + ")"]
                    spreadsheet.append_data([item_row, [None]])
                    spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                    s_row = s_row + 2
                # Add detail from schedule
                else:
                    row = [code, desc, unit, qty]
                    spreadsheet.append_data([row, [None]])
                    spreadsheet.set_style(s_row, 1, horizontal="center", vertical="top")
                    s_row = s_row + 2

    spreadsheet.set_column_widths([10, 50, 20, 10, 10, 10, 10, 10, 10, 10, 10])
    spreadsheet.set_page_settings(font="Consolas")

    log.info("ScheduleDatabase - export_meas_spreadsheet - Details of Measurement exported")
