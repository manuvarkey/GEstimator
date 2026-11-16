import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from modern.backend import dictionary, metadata
from modern.backend.mcp_operations import execute
from modern.backend.search import Index
from modern.backend.service import Service


class MCPSearchTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        self.s.mcp.access = "read-write"
        self.addCleanup(self.s.close)

    def tool(self, name, **args):
        return execute(self.s, name, args)["data"]

    def test_normalization_case_ambiguity_extraction_and_layer_precedence(self):
        self.assertEqual(dictionary.normalize("2X4 sq.mm 16 Amps dia nos mm² cu.m"), "2 x 4 sq mm 16 amp diameter number sq mm cum")
        found = dictionary.extract("residual current circuit breaker (RCCB), miniature circuit breaker (MCB)")
        self.assertEqual([e["term"] for e in found], ["RCCB", "MCB"])
        self.assertIn("damp proof course", dictionary.expand("DPC", dictionary.entries(""), "CIVIL"))
        self.assertNotIn("damp proof", dictionary.expand("dpc", dictionary.entries(""), "CIVIL"))
        self.assertNotIn("chrome plated", dictionary.expand("CP&OH", dictionary.entries(""), "PLUMBING"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dictionary.user.json"
            path.write_text(json.dumps([dict(term="CUSTOM", expand=["user meaning"])]))
            entries = dictionary.entries("", dict(dictionary=[dict(term="CUSTOM", expand=["generated meaning"])]), path)
            self.assertEqual(next(e for e in entries if e["term"] == "CUSTOM")["expand"], ["user meaning"])
            before = dictionary.fingerprint(entries)
            path.write_text(json.dumps([dict(term="CUSTOM", expand=["changed meaning"])]))
            self.assertNotEqual(dictionary.fingerprint(dictionary.entries("", {}, path)), before)

    def test_bundled_search_and_automatic_abbreviation_extraction_without_a_project(self):
        result = self.tool("search_items", source="bundled:DSREM2022.eproj", kind="schedule", query="modular switch light point PVC conduit", limit=5)
        self.assertIn("1.10.1", [row["code"] for row in result["items"]])
        self.assertFalse(self.s.state()["project_open"])
        entries = self.tool("describe_source", source="bundled:DSREM2022.eproj", section="dictionary")["entries"]
        self.assertTrue(any(e["term"] == "RCCB" and any("residual" in x.casefold() for x in e["expand"]) for e in entries))
        self.assertTrue(any(e["term"] == "MCB" and any("miniature" in x.casefold() for x in e["expand"]) for e in entries))

    def test_custom_source_without_metadata_search_cache_undo_and_clear_enrichment(self):
        self.tool("project", action="new")
        self.tool("upsert_items", kind="schedule", items=[dict(code="A", description="Copper wire", category="Electrical", rate="1")])
        self.assertEqual(self.tool("search_items", kind="schedule", query="copper")["items"][0]["code"], "A")
        before = self.s._mcp_search.copy()
        self.tool("search_items", kind="schedule", query="wire")
        self.assertEqual(self.s._mcp_search, before)
        self.tool("upsert_items", kind="schedule", items=[dict(code="A", description="Steel pipe")])
        self.assertEqual(self.tool("search_items", kind="schedule", query="copper")["items"], [])
        self.tool("history", action="undo")
        self.assertEqual(self.tool("search_items", kind="schedule", query="copper")["items"][0]["code"], "A")
        metadata.write(self.s.db, dict(schema=1, provenance=dict(generator="ai", reviewed=False), database=dict(summary="Example enrichment"), items={"A":dict(short="Conductors", keywords=["unicornterm"])}))
        self.assertEqual(self.tool("search_items", kind="schedule", query="unicornterm")["items"][0]["short"], "Conductors")
        self.assertTrue(self.tool("describe_source")["ai_generated"])
        self.assertEqual(self.s.call("schedule.editor.state", {})["enrichment"]["summary"], "Example enrichment")
        self.s.call("project.enrichment.clear", dict(revision=self.s.revision))
        self.assertEqual(self.tool("search_items", kind="schedule", query="unicornterm")["items"], [])
        self.tool("history", action="undo")
        self.assertEqual(self.tool("search_items", kind="schedule", query="unicornterm")["items"][0]["code"], "A")
        self.assertNotIn("meta_enrichment", self.tool("describe_source", section="schema")["views"])

    def test_malformed_optional_enrichment_falls_back_to_source_data(self):
        self.tool("project", action="new")
        self.tool("upsert_items", kind="schedule", items=[dict(code="A", description="Copper conductor", category="Electrical")])
        metadata.write(self.s.db, dict(schema=1, provenance=dict(generator="ai")))
        self.s.db.database.execute_sql("UPDATE meta_enrichment SET data=?", (json.dumps(dict(schema=1, database="bad", items={"A":None})),))
        self.assertEqual(metadata.read(self.s.db), {})
        self.assertEqual(self.tool("search_items", kind="schedule", query="copper")["items"][0]["code"], "A")
        self.assertIsNone(self.s.call("schedule.editor.state", {})["enrichment"])

    def test_bm25_fallback_and_empty_search(self):
        import sqlite3
        from unittest.mock import Mock
        connection = sqlite3.connect(":memory:")
        proxy = Mock(wraps=connection)
        def without_fts(sql, *args):
            if "CREATE VIRTUAL TABLE" in sql:
                raise sqlite3.OperationalError("no such module: fts5")
            return connection.execute(sql, *args)
        proxy.execute.side_effect = without_fts
        with patch("modern.backend.search.sqlite3.connect", return_value=proxy):
            index = Index([dict(code="A", category="Work", unit="m"), dict(code="B", category="Work", unit="m")], ["copper wire", "concrete block"])
        self.addCleanup(index.close)
        self.assertFalse(index.fts)
        self.assertEqual(index.rank("copper", 5)[0]["code"], "A")
        self.assertEqual(index.rank("", 5), [])

    def test_evaluation_has_thirty_queries_per_bundled_database(self):
        data = json.loads((Path(__file__).parent / "data/search_eval.json").read_text())
        self.assertEqual(set(data["databases"]), {"DSREM2022.eproj", "DSR2021.eproj"})
        self.assertTrue(all(len(cases) >= 30 for cases in data["databases"].values()))
