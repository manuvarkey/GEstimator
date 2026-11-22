import os
from pathlib import Path
import re
import tempfile
import unittest
from modern.backend import mcp_skills
from modern.backend.mcp_operations import execute, ToolError
from modern.backend.mcp_server import INSTRUCTIONS
from modern.backend.service import Service
from tests.test_mcp_server import MCPFixture

SKILLS = ("civil-measurement-estimation", "electrical-measurement-estimation", "preliminary-lighting-design")
LINK = re.compile(r"gestimator://skills/[^\s)\]>`'\"]+")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PackagedSkills(unittest.TestCase):
    def test_exactly_three_skills_with_descriptions(self):
        resources = mcp_skills.list_resources()
        skills = [r for r in resources if r["uri"].count("/") == 3]
        self.assertEqual([r["uri"] for r in skills], ["gestimator://skills/" + name for name in SKILLS])
        self.assertEqual(len(list(mcp_skills.ROOT.glob("*/SKILL.md"))), 3)
        for resource in resources:
            self.assertEqual(resource["mimeType"], "text/markdown")
            self.assertTrue(20 <= len(resource["description"]) <= 400, resource["uri"])
            self.assertGreater(resource["size"], 0)
        self.assertEqual({r["annotations"]["priority"] for r in skills}, {1.0})

    def test_skill_content_and_required_sections(self):
        for name in SKILLS:
            text = mcp_skills.read_resource("gestimator://skills/" + name)["contents"][0]["text"]
            self.assertIn(f"name: {name}\n", text)
        for name in SKILLS[:2]:
            text = mcp_skills.read_resource("gestimator://skills/" + name)["contents"][0]["text"]
            self.assertIn("## 3. Design inputs and checks", text)
            self.assertIn("Present, then apply on request", text)
        lighting = mcp_skills.read_resource("gestimator://skills/preliminary-lighting-design")["contents"][0]["text"]
        self.assertIn("Handoff to electrical measurement", lighting)
        example = mcp_skills.read_resource("gestimator://skills/preliminary-lighting-design/references/worked-example.md")["contents"][0]["text"]
        for text in ("## Draft measurement", "## Proposed schedule item matches", "8.7.4", "1.10.3", "1.55.3"):
            self.assertIn(text, example)

    def test_every_link_resolves_and_every_reference_is_linked(self):
        resources = {r["uri"] for r in mcp_skills.list_resources()}
        linked = set()
        for uri in resources:
            text = mcp_skills.read_resource(uri)["contents"][0]["text"]
            for link in LINK.findall(text):
                self.assertIn(link, resources, f"{uri} links to {link}")
                linked.add(link)
        references = {uri for uri in resources if uri.count("/") > 3}
        self.assertGreaterEqual(len(references), 10)
        self.assertEqual(references - linked, set())

    def test_invalid_and_unknown_uris_are_rejected(self):
        for uri in (None, 7, "", "gestimator://skills/", "gestimator://skills/unknown", "file:///etc/passwd",
                    "gestimator://skills/../mcp_server.py", "gestimator://skills/civil-measurement-estimation/../../mcp_skills.py",
                    "gestimator://skills/civil-measurement-estimation/%2e%2e/%2e%2e/mcp_skills.py",
                    "gestimator://skills/civil-measurement-estimation/references/missing.md",
                    "gestimator://skills/civil-measurement-estimation/SKILL.md",
                    "gestimator://skills/civil-measurement-estimation/references/masonry.md?x=1",
                    "GESTIMATOR://skills/civil-measurement-estimation", "gestimator://skills/" + "a" * 400):
            with self.assertRaises(mcp_skills.ResourceNotFound, msg=repr(uri)):
                mcp_skills.read_resource(uri)


class SkillPackages(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "skills"
        self.outside = Path(directory.name) / "secret.md"
        write(self.outside, "---\ndescription: outside\n---\nsecret\n")

    def test_new_package_needs_only_content_and_metadata(self):
        self.assertEqual(mcp_skills.list_resources(self.root), [])
        write(self.root / "plumbing-estimation/SKILL.md", "---\nname: plumbing-estimation\ndescription: Plumbing takeoff.\n---\n# Plumbing\n")
        write(self.root / "plumbing-estimation/references/pipes.md", "---\ndescription: Pipe runs.\n---\n# Pipes\n")
        uris = [r["uri"] for r in mcp_skills.list_resources(self.root)]
        self.assertEqual(uris, ["gestimator://skills/plumbing-estimation", "gestimator://skills/plumbing-estimation/references/pipes.md"])
        listed = mcp_skills.list_resources(self.root)
        self.assertEqual((listed[0]["title"], listed[1]["title"]), ("Plumbing", "Pipes"))
        self.assertIn("# Pipes", mcp_skills.read_resource(uris[1], self.root)["contents"][0]["text"])

    def test_packages_without_valid_metadata_or_names_are_skipped(self):
        write(self.root / "no-description/SKILL.md", "---\nname: no-description\n---\n")
        write(self.root / "wrong-name/SKILL.md", "---\nname: other\ndescription: x\n---\n")
        write(self.root / "Upper_Case/SKILL.md", "---\nname: Upper_Case\ndescription: x\n---\n")
        write(self.root / "good/SKILL.md", "---\nname: good\ndescription: Good.\n---\n")
        write(self.root / "good/references/undescribed.md", "# No front matter\n")
        write(self.root / "good/references/Bad Name.md", "---\ndescription: x\n---\n")
        write(self.root / "good/notes.txt", "not markdown")
        (self.root / "good/references/binary.md").write_bytes(b"---\ndescription: x\n---\n\xff\xfe")
        with self.assertLogs("modern.backend.mcp_skills", "WARNING") as logs:
            self.assertEqual([r["uri"] for r in mcp_skills.list_resources(self.root)], ["gestimator://skills/good"])
            with self.assertRaises(mcp_skills.ResourceNotFound):
                mcp_skills.read_resource("gestimator://skills/good/references/undescribed.md", self.root)
        self.assertTrue(any("no-description" in line for line in logs.output))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinks_outside_the_packages_are_not_served(self):
        write(self.root / "good/SKILL.md", "---\nname: good\ndescription: Good.\n---\n")
        try:
            (self.root / "good/leak.md").symlink_to(self.outside)
            (self.root / "linked").symlink_to(self.outside.parent, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks not permitted")
        self.assertEqual([r["uri"] for r in mcp_skills.list_resources(self.root)], ["gestimator://skills/good"])
        for uri in ("gestimator://skills/good/leak.md", "gestimator://skills/linked"):
            with self.assertRaises(mcp_skills.ResourceNotFound):
                mcp_skills.read_resource(uri, self.root)


class SkillsThroughTools(unittest.TestCase):
    """Clients that ignore server instructions and resources still meet the
    skills: get_state lists them and describe_source reads them."""

    def setUp(self):
        self.s = Service()
        self.addCleanup(self.s.close)

    def test_get_state_lists_skills_and_start_here_without_a_project(self):
        state = execute(self.s, "get_state", {})["data"]
        self.assertFalse(state["project_open"])
        self.assertEqual(list(state)[:2], ["start_here", "skills"])
        self.assertIn("measurements", state["start_here"])
        self.assertEqual([s["skill"] for s in state["skills"]], list(SKILLS))
        self.assertEqual(state["skills"][0]["read"], "describe_source section=skill:civil-measurement-estimation")

    def test_describe_source_reads_skills_and_references_without_a_project(self):
        listing = execute(self.s, "describe_source", dict(section="skills"))["data"]["skills"]
        self.assertEqual([s["skill"] for s in listing], list(SKILLS))
        self.assertIn("references/masonry.md", [r["path"] for r in listing[0]["references"]])
        skill = execute(self.s, "describe_source", dict(section="skill:civil-measurement-estimation"))["data"]
        self.assertIn("name: civil-measurement-estimation", skill["text"])
        self.assertIn("skill:civil-measurement-estimation/references/masonry.md", [r["section"] for r in skill["references"]])
        for section in ("skill:civil-measurement-estimation/references/masonry.md", "gestimator://skills/civil-measurement-estimation/references/masonry.md"):
            data = execute(self.s, "describe_source", dict(section=section))["data"]
            self.assertIn("IS 1200 (Part 3)", data["text"])
            self.assertNotIn("references", data)
        for section in ("skill:nope", "skill:../x", "gestimator://skills/civil-measurement-estimation/../../x.md"):
            with self.assertRaises(ToolError) as error:
                execute(self.s, "describe_source", dict(section=section))
            self.assertEqual(error.exception.detail["code"], "not_found")
        with self.assertRaises(ToolError):
            execute(self.s, "describe_source", dict(section="overview"))  # project source still needs a project

    def test_import_warns_about_unread_notes_and_overview_puts_notes_first(self):
        self.s.mcp.access = "read-write"
        execute(self.s, "project", dict(action="new"))
        source = "bundled:DSREM2025.eproj"
        result = execute(self.s, "import_items", dict(source=source, kind="schedule", codes=["1.10.3"]))
        warning = next(w for w in result["warnings"] if w.get("code") == "notes_not_read")
        self.assertEqual(warning["sections"], ["overview", "category:WIRING"])
        overview = execute(self.s, "describe_source", dict(source=source))["data"]
        self.assertEqual(list(overview)[0], "metadata")
        execute(self.s, "describe_source", dict(source=source, section="category:WIRING"))
        result = execute(self.s, "import_items", dict(source=source, kind="schedule", codes=["1.55.3"]))
        self.assertFalse([w for w in result["warnings"] if w.get("code") == "notes_not_read"])


class SkillResourcesOverHTTP(MCPFixture):
    def rpc(self, method, params=None):
        status, message = self.http(message=dict(jsonrpc="2.0", id=9, method=method, params=params or {}))
        self.assertEqual(status, 200)
        return message

    def test_listing_and_reading_without_a_project_in_read_only_mode(self):
        self.start()
        self.assertEqual(self.runtime.call("mcp.status")["access"], "read")
        self.assertFalse(self.tool("get_state")["structuredContent"]["data"]["project_open"])
        initialized = self.rpc("initialize", dict(protocolVersion="2025-11-25", capabilities={}, clientInfo=dict(name="test", version="1")))["result"]
        self.assertEqual(initialized["capabilities"]["resources"], dict(listChanged=False))
        self.assertIn("gestimator://skills/", initialized["instructions"])
        self.assertLess(len(INSTRUCTIONS.split()), 230)
        resources = self.rpc("resources/list")["result"]["resources"]
        self.assertEqual(resources, mcp_skills.list_resources())
        self.assertEqual(self.rpc("resources/templates/list")["result"], dict(resourceTemplates=[]))
        for name in SKILLS:
            contents = self.rpc("resources/read", dict(uri="gestimator://skills/" + name))["result"]["contents"]
            self.assertEqual(contents[0]["uri"], "gestimator://skills/" + name)
            self.assertEqual(contents[0]["mimeType"], "text/markdown")
            self.assertIn(f"name: {name}", contents[0]["text"])
        reference = "gestimator://skills/civil-measurement-estimation/references/masonry.md"
        self.assertIn("IS 1200 (Part 3)", self.rpc("resources/read", dict(uri=reference))["result"]["contents"][0]["text"])
        self.assertEqual(self.runtime.call("mcp.status")["last_activity"], "Resource: " + reference)
        self.assertFalse(self.tool("get_state")["structuredContent"]["data"]["project_open"])

    def test_invalid_reads_return_protocol_errors(self):
        self.start()
        missing = self.rpc("resources/read", dict(uri="gestimator://skills/../../etc/passwd"))["error"]
        self.assertEqual((missing["code"], missing["data"]["uri"]), (-32002, "gestimator://skills/../../etc/passwd"))
        self.assertEqual(self.rpc("resources/read", dict(uri="gestimator://skills/nope"))["error"]["code"], -32002)
        self.assertEqual(self.rpc("resources/read", {})["error"]["code"], -32602)
        self.assertEqual(self.rpc("resources/read", dict(uri=["x"]))["error"]["code"], -32602)
        self.assertEqual(self.http(message=dict(jsonrpc="2.0", id=1, method="resources/list"), headers={"Authorization": "Bearer wrong"})[0], 401)


if __name__ == "__main__":
    unittest.main()
