"""Check the MCP workflow for categories and combined measurement sheets."""

from decimal import Decimal

from test_mcp_server import MCPFixture


class MCPMeasurementGroupTests(MCPFixture):
    def call_tool(self, name, **arguments):
        result = self.tool(name, arguments)
        self.assertFalse(result["isError"], result)
        return result["structuredContent"]["data"]

    def test_category_refs_and_multi_output_quantities(self):
        self.runtime.call("mcp.configure", {"access": "read-write"})
        self.start()
        self.call_tool("project", action="new")
        self.call_tool(
            "upsert_items",
            kind="schedule",
            items=[
                {"code": code, "description": code, "unit": unit}
                for code, unit in [("LIGHT", "Each"), ("POINT", "Point"), ("LOOP", "Point"), ("CABLE", "m")]
            ],
        )

        # Create two groups and link independent outputs in one transaction.
        result = self.call_tool(
            "edit_measurements",
            ops=[
                {"action": "create", "description": "First floor lighting", "ref": "lighting"},
                {
                    "action": "create",
                    "template": "_3_NNNNNNNN",
                    "description": "Fixtures and points",
                    "after": "$lighting",
                    "ref": "fixtures",
                    "links": [{"code": "LIGHT"}, {"code": "POINT"}, {"code": ""}, {"code": "LOOP"}],
                    "records": [
                        {"Description": "Office", "N1": "2*3", "N2": "2", "N4": "4"},
                        {"Description": "Corridor", "N1": "3", "N2": "1", "N4": "2"},
                    ],
                },
                {"action": "create", "description": "Second floor power", "ref": "power", "after": "$lighting"},
                {
                    "action": "create",
                    "template": "_2_LLLLL",
                    "description": "Cable runs",
                    "after": "$power",
                    "ref": "cables",
                    "links": [{"code": "CABLE"}],
                    "records": [{"L1": "12.5"}],
                },
            ],
        )
        refs = result["refs"]
        items = self.call_tool("get_measurements")["items"]
        self.assertEqual(
            [item["id"] for item in items], [refs[key] for key in ("lighting", "fixtures", "power", "cables")]
        )
        self.assertEqual(
            [item["description"] for item in items if item["type"] == "Heading"],
            ["First floor lighting", "Second floor power"],
        )
        self.call_tool("history", action="undo")
        self.assertEqual(self.call_tool("get_measurements")["items"], [])
        self.call_tool("history", action="redo")

        self.call_tool("recalculate", what="quantities", rounding="No rounding")
        rows = self.call_tool("get_items", kind="schedule", codes=["LIGHT", "POINT", "LOOP", "CABLE"])["items"]
        self.assertEqual(
            {row["code"]: Decimal(row["qty"]) for row in rows},
            {"LIGHT": Decimal(9), "POINT": Decimal(3), "LOOP": Decimal(6), "CABLE": Decimal("12.5")},
        )
