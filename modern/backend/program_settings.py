"""Validate application preferences while retaining the legacy calculation rules."""

import copy
import re
from pathlib import Path

import appdirs

from estimator import misc
from estimator.data.schedule import Currency, ScheduleItemModel

from .numbers import decimal

KINDS = ("Group", "Subtotal", "Weight", "Multiply", "Round")


def template_rows(items):
    return [
        dict(
            kind=KINDS[row["itemtype"]],
            description=row["description"],
            code=row.get("code", ""),
            value=str(row.get("value", "")),
        )
        for row in items
    ]


def library_directory():
    return (
        Path(appdirs.AppDirs(misc.PROGRAM_NAME, misc.PROGRAM_AUTHOR, version=misc.PROGRAM_VER).user_data_dir)
        / "database"
    )


def library_catalog():
    rows, warnings = [], []
    for folder, bundled in ((Path(misc.abs_path("database")), True), (library_directory(), False)):
        try:
            if not folder.exists():
                continue
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.suffix.lower() == ".eproj":
                    rows.append(
                        dict(
                            name=path.stem,
                            path="bundled:" + path.name if bundled else str(path.resolve()),
                            bundled=bundled,
                        )
                    )
        except OSError as error:
            warnings.append(str(error))
    return dict(rows=rows, warnings=warnings)


def defaults():
    return dict(
        export_break_items=True,
        live_search=False,
        enter_edits_next_cell=False,
        sch_rate_mult_factor="1",
        ana_copy_delete_rows=0,
        number_locale="",
        currency_code="INR",
        show_currency_symbol=False,
        mcp_enabled=False,
        ana_default_rows=template_rows(misc.ana_default_add_items),
        ana_copy_rows=[],
    )


def text(value):
    if not isinstance(value, str) or len(value) > 10000:
        raise ValueError("Template text must be at most 10000 characters")
    return value


def validate_rows(rows, *, parse_number=decimal):
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Use at most 100 template rows")
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") not in KINDS:
            raise ValueError("Unknown template row type")
        kind = row["kind"]
        description = text(row.get("description", ""))
        code = text(row.get("code", "")) if kind == "Group" else ""
        value = ""
        if kind in ("Weight", "Multiply", "Round"):
            number = parse_number(row.get("value", ""))
            if kind == "Round" and (
                abs(number) > 12 or (number != int(number) and int((number - int(number)) * 10) == 0)
            ):
                raise ValueError("Unsupported template rounding places")
            value = str(number)
        result.append(dict(kind=kind, description=description, code=code, value=value))
    return result


def validate(settings):
    if not isinstance(settings, dict):
        raise ValueError("Invalid program settings")
    base = defaults()
    base.update({key: settings[key] for key in base if key in settings})
    if type(base["export_break_items"]) is not bool:
        raise ValueError("Choose whether exported descriptions should be split")
    if type(base["live_search"]) is not bool:
        raise ValueError("Choose whether to search as you type")
    if type(base["enter_edits_next_cell"]) is not bool:
        raise ValueError("Choose whether Enter edits the next cell")
    if type(base["mcp_enabled"]) is not bool:
        raise ValueError("Choose whether the MCP server is enabled")
    locale = base["number_locale"]
    if not isinstance(locale, str) or (locale and not re.fullmatch(r"[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8}){0,4}", locale)):
        raise ValueError("Choose a valid regional locale, such as en-IN")
    if not isinstance(base["currency_code"], str) or not re.fullmatch(r"[A-Z]{3}", base["currency_code"]):
        raise ValueError("Use a three-letter currency code, such as INR")
    if type(base["show_currency_symbol"]) is not bool:
        raise ValueError("Choose whether to display currency symbols")
    factor = decimal(base["sch_rate_mult_factor"])
    count = base["ana_copy_delete_rows"]
    if type(count) is not int or not 0 <= count <= 5:
        raise ValueError("Choose between 0 and 5 trailing analysis rows")
    base["sch_rate_mult_factor"] = str(Currency(factor, 5))
    for key in ("ana_default_rows", "ana_copy_rows"):
        base[key] = validate_rows(base[key])
    return base


def legacy_rows(rows, *, parse_number=decimal):
    result = []
    for row in validate_rows(rows, parse_number=parse_number):
        kind = KINDS.index(row["kind"])
        value = dict(itemtype=kind, description=row["description"])
        if kind == 0:
            value.update(code=row["code"], resource_list=[])
        elif kind in (2, 3, 4):
            value["value"] = parse_number(row["value"])
        result.append(value)
    # Exercise the original engine, including interval rounding, without a project.
    model = ScheduleItemModel("", "")
    model.ana_items = copy.deepcopy(result)
    model.evaluate_results()
    return result
