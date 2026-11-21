"""Sample estimate for the user manual screenshots.

Usage: python -m modern.e2e.create_sample_project <path.eproj>

Builds a small residential building estimate from the bundled DSR 2023
database through the same tool operations the MCP server offers, with
measurements linked to the schedule items, and saves it to the given path.
"""

import os
import sys
from pathlib import Path

from modern.backend.runtime import Runtime

ROOT = Path(__file__).resolve().parents[2]
# Code, measurement title, measured quantities as (description, No, L, B, H).
ITEMS = {
    "2.6.1": ("Excavation for foundations", [("Footings F1", "8", "1.8", "1.8", "1.5"), ("Wall footings", "1", "42.0", "0.9", "0.9")]),
    "4.1.8": ("PCC 1:4:8 below footings", [("Footings F1", "8", "1.8", "1.8", "0.1"), ("Wall footings", "1", "42.0", "0.9", "0.1")]),
    "5.1.2": ("RCC in footings", [("Footings F1", "8", "1.5", "1.5", "0.45")]),
    "5.3": ("RCC in roof slab and beams", [("Roof slab", "1", "12.0", "8.0", "0.125"), ("Beams B1", "4", "8.0", "0.23", "0.3")]),
    "5.9.1": ("Shuttering for footings", [("Footings F1 sides", "8", "6.0", "", "0.45")]),
    "5.9.3": ("Shuttering for roof slab", [("Roof slab soffit", "1", "12.0", "8.0", "")]),
    "5.22.6": ("Reinforcement", [("Footings and slab, from bar bending schedule", "1", "2850", "", "")]),
    "6.1.2": ("Brick work in plinth", [("Plinth walls", "1", "42.0", "0.35", "0.6")]),
    "13.1.2": ("Plaster on external walls", [("External walls", "1", "40.0", "", "3.2"), ("Deduct door", "-2", "1.0", "", "2.1")]),
    "13.82.2": ("Painting internal walls", [("Internal walls", "1", "96.0", "", "3.0")]),
}


def main(path):
    runtime = Runtime(None)
    call = runtime.call

    def tool(name, **arguments):
        result = call("mcp.read", dict(name=name, arguments=arguments))
        if result.get("isError"):
            raise RuntimeError(result)
        return result.get("structuredContent", result)

    call("mcp.configure", dict(access="read-write"))  # in memory; the server is not started
    call("project.new", dict(discard=True))
    library = call("library.attach", dict(path=str(ROOT / "estimator/database/DSR2023.eproj")))[0]["id"]
    tool("project", action="set_settings", settings=dict(project_name="Staff Quarters, Block A", project_item_code="", project_resource_code=""))
    tool("import_items", source=library, kind="schedule", codes=list(ITEMS))
    # Sub-analyses the imported analyses use come first; show the estimate items first.
    tool("move_items", kind="category", category_kind="schedule", codes=["SUB ANALYSIS"], position=dict(after="FINISHING"))
    ops = []
    for index, (code, (title, records)) in enumerate(ITEMS.items()):
        ops.append(dict(action="create", template="_1_NLBH", description=title, links=[dict(code=code, remark="")], ref=f"m{index}",
                        records=[dict(c0=d, c2=n, c3=l, c4=b, c5=h) for d, n, l, b, h in records], **(dict(after=f"$m{index - 1}") if index else {})))
    tool("edit_measurements", ops=ops)
    tool("recalculate", what="quantities")
    tool("project", action="save_copy", path=str(Path(path).resolve()))


if __name__ == "__main__":
    code = 0
    try:
        main(sys.argv[1])
    except Exception:
        import traceback
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    # The backend worker thread does not stop on its own.
    os._exit(code)
