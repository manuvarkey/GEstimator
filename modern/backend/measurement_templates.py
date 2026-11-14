"""Presentation metadata for the installed Python measurement templates."""

from pathlib import Path
from estimator import misc
from estimator.data.measurement import MeasurementItemCustom

DESCRIPTIONS = {
    "_1_NLBH": ("Dimensions (N × L × B × H)", "Multiply the nonzero factors in each record and sum the record totals.", "Blank and zero factors are ignored, not multiplied as zero. A completely empty record totals zero."),
    "_2_LLLLL": ("Five linked quantities", "Five independent quantity columns, each linked to its own schedule item.", "Each quantity is rounded to three places per record before summing."),
    "_3_NNNNNNNN": ("Eight linked quantities", "Eight independent quantity columns, each linked to its own schedule item.", "Each quantity is rounded to three places per record before summing."),
    "_4_nnnnnT": ("Sum of five quantities", "Add N1 to N5 in each record and sum the record totals.", "Negative quantities are included; record totals are rounded to three places."),
    "civil_steel_table": ("Steel reinforcement", "Multiply two counts by six bar lengths; apply the six configured mass-per-length constants.", "Set bar labels and constants in Properties. Fractional counts remain in calculations; constants must be valid numbers."),
    "elec_tableofpoints": ("Electrical points", "Sum Lights, Fans, Exhaust Fans, Call Bells and Other as whole counts.", "Each count is truncated towards zero before summing, matching the original template."),
    "elec_ac_round_duct": ("Round ducting", "Calculate π × (D1 + D2) × (L1 + L2) / 4,000,000 using millimetres.", "The original template retains fractional dimensions in calculations; record areas are rounded to three places."),
    "elec_ac_rect_duct": ("Rectangular ducting", "Calculate (H1 + W1 + H2 + W2) × (L1 + L2) / 2,000,000 using millimetres.", "The original template retains fractional dimensions in calculations; record areas are rounded to three places."),
}


def metadata(item):
    label, summary, note = DESCRIPTIONS.get(item.itemtype, (item.name, "Installed measurement template.", "Results are calculated by the installed Python template."))
    return dict(code=item.itemtype, name=item.name, label=label, summary=summary, note=note,
                inputs=[caption for caption, kind in zip(item.captions, item.columntypes) if kind != misc.MEAS_CUST],
                outputs=len(item.itemnos), properties=bool(item.captions_udata))


def catalog():
    return [metadata(MeasurementItemCustom(plugin=path.stem))
            for path in sorted(Path(misc.abs_path("meas_templates")).glob("*.py")) if path.stem != "__init__"]


def column_title(item, index):
    title = item.captions[index]
    for mapping, remark in zip(item.itemnos_mapping, item.item_remarks):
        if mapping == index and remark:
            title += " · " + remark
    if item.itemtype == "civil_steel_table" and 10 <= index <= 15:
        title += " · " + str(item.user_data[index - 10])
    return title


def link_label(item, index):
    mapping = item.itemnos_mapping[index]
    return item.captions[mapping] if mapping is not None else "Measured quantity"


def property_groups(item):
    fields = [dict(index=index, caption=caption, numeric=kind in (misc.MEAS_L, misc.MEAS_NO))
              for index, (caption, kind) in enumerate(zip(item.captions_udata, item.columntypes_udata))]
    if item.itemtype == "civil_steel_table":
        return [dict(label="Bar " + str(index + 1), fields=[dict(fields[index], label="Label"), dict(fields[index + 6], label="Mass / length")]) for index in range(6)]
    return [dict(label=field["caption"], fields=[dict(field, label=field["caption"])]) for field in fields]
