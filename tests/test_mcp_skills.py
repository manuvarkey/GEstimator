"""Estimation skill library discovery, selection and public MCP resources."""

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modern.backend import mcp_skills
from modern.backend.mcp_operations import ToolError, execute
from modern.backend.mcp_server import INSTRUCTIONS
from modern.backend.service import Service
from tests.test_mcp_server import MCPFixture

GENERIC = ("generic/civil-takeoff", "generic/electrical-takeoff")
IN = ("in/civil-measurement-estimation", "in/electrical-measurement-estimation", "in/preliminary-lighting-design")
SHARED = ("shared/rate-analysis",)
LINK = re.compile(r"gestimator://skills/[^\s)\]>`'\"]+")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install(root, folder="office", identity="office", skill="rate-analysis"):
    library = root / folder
    write(library / "library.json", json.dumps(dict(schema_version=1, id=identity, name="Office library")))
    package = library / skill
    write(package / "SKILL.md", f"---\nname: {skill}\ndescription: Office estimates.\n---\n# Office workflow\n")
    return package


def addresses(catalog):
    return [skill["uri"][len(mcp_skills.SCHEME) :] for skill in catalog.skills()]


class PackagedSkills(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.libraries = mcp_skills.SkillLibraries(user=Path(root.name))

    def test_packaged_manifests_and_resources(self):
        self.assertEqual(self.libraries.status()["issues"], [])
        self.assertEqual([entry["id"] for entry in self.libraries.status()["libraries"]], ["generic", "in"])
        self.assertEqual(addresses(self.libraries.active), list(GENERIC + SHARED))
        self.libraries.select("in")
        catalog = self.libraries.active
        self.assertEqual(addresses(catalog), list(IN + SHARED))
        for resource in catalog.list_resources():
            self.assertEqual(resource["mimeType"], "text/markdown")
            self.assertTrue(20 <= len(resource["description"]) <= 400, resource["uri"])
            self.assertGreater(resource["size"], 0)
        for key in IN[:2]:
            text = catalog.read_resource(mcp_skills.SCHEME + key)["contents"][0]["text"]
            self.assertIn("## 3. Design inputs and checks", text)
            self.assertIn("Present, then apply on request", text)

        example = catalog.read_resource(mcp_skills.SCHEME + IN[2] + "/references/worked-example.md")["contents"][0][
            "text"
        ]
        for text in ("## Draft measurement", "## Proposed schedule item matches", "8.7.4", "1.10.3", "1.55.3"):
            self.assertIn(text, example)

    def test_every_bundled_link_resolves_and_every_reference_is_linked(self):
        self.libraries.select("in")
        catalog = self.libraries.active
        resources = {resource["uri"] for resource in catalog.list_resources()}
        linked = set()
        for uri in resources:
            for link in LINK.findall(catalog.read_resource(uri)["contents"][0]["text"]):
                self.assertIn(link, resources, f"{uri} links to {link}")
                linked.add(link)
        references = {uri for uri in resources if uri.count("/") > 4}
        self.assertGreaterEqual(len(references), 10)
        self.assertEqual(references - linked, set())

    def test_only_documents_in_the_selected_library_and_shared_are_readable(self):
        self.libraries.select("in")
        for relative in (
            GENERIC[0],
            "unknown",
            "../mcp_skills.py",
            "in/../shared/rate-analysis",
            IN[0] + "/%2e%2e/secret.md",
            IN[0] + "/SKILL.md",
            IN[0] + "/references/masonry.md?x=1",
            "a" * 400,
        ):
            with self.assertRaises(mcp_skills.ResourceNotFound):
                self.libraries.active.read_resource(mcp_skills.SCHEME + relative)


class UserLibraries(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.libraries = mcp_skills.SkillLibraries(user=self.root / "libraries")

    def test_refresh_publishes_documents_together_and_keeps_sets_independent(self):
        self.assertFalse(self.libraries.user.exists())
        self.assertEqual(self.libraries.open_directory(), str(self.libraries.user))
        package = install(self.libraries.user)
        uri = mcp_skills.SCHEME + "office/rate-analysis"
        reference = uri + "/references/rules.md"
        write(package / "references/rules.md", "---\ndescription: Office rules.\n---\n# Rules\n")
        write(package / "references/draft.MD", "---\ndescription: Draft.\n---\n")
        self.libraries.select("office")
        self.assertEqual(self.libraries.status()["active_library"], "generic")
        self.libraries.refresh()
        previous = self.libraries.active
        self.assertEqual(addresses(previous), ["office/rate-analysis", "shared/rate-analysis"])
        self.assertEqual(len(previous.list_resources()), 3)
        self.assertIn("# Rules", previous.read_resource(reference)["contents"][0]["text"])

        # Content and metadata change together at refresh, including for readers
        # holding the previous snapshot after the on-disk library was removed.
        (package / "references/rules.md").unlink()
        self.assertIn("# Rules", previous.read_resource(reference)["contents"][0]["text"])
        self.libraries.refresh()
        with self.assertRaises(mcp_skills.ResourceNotFound):
            self.libraries.active.read_resource(reference)
        (package / "SKILL.md").unlink()
        status = self.libraries.refresh()
        self.assertEqual((status["active_library"], status["requested_library"]), ("generic", "office"))
        self.assertIn("no readable skill packages", "\n".join(status["issues"]))
        install(self.libraries.user)
        self.assertEqual(self.libraries.refresh()["active_library"], "office")

    def test_invalid_manifests_and_duplicate_ids_are_reported(self):
        install(self.libraries.user, folder="valid")
        install(self.libraries.user, folder="z-copy")
        install(self.libraries.user, folder="overrides-in", identity="in")
        install(self.libraries.user, folder="overrides-shared", identity="shared")
        write(self.libraries.user / "bad/library.json", "{oops")
        write(self.libraries.user / "wrong-version/library.json", '{"schema_version":2}')
        write(self.libraries.user / "malformed/library.json", "[" * 10000)
        status = self.libraries.refresh()
        self.assertEqual([entry["id"] for entry in status["libraries"]], ["generic", "in", "office"])
        issues = "\n".join(status["issues"])
        for name in ("bad", "wrong-version", "malformed", "z-copy", "overrides-in", "overrides-shared"):
            self.assertIn(name + ":", issues)
        self.assertIn("Duplicate or reserved library ID", issues)
        with self.assertRaises(ValueError):
            self.libraries.select("shared")

    def test_symlinked_libraries_packages_and_files_are_skipped(self):
        package = install(self.libraries.user)
        outside = install(self.root / "outside", identity="outside")
        try:
            (self.libraries.user / "linked").symlink_to(outside.parent, target_is_directory=True)
            (package.parent / "linked-skill").symlink_to(outside, target_is_directory=True)
            (package / "leak.md").symlink_to(outside / "SKILL.md")
        except OSError:
            self.skipTest("symlinks not permitted")
        status = self.libraries.refresh()
        self.assertNotIn("outside", [library["id"] for library in status["libraries"]])
        self.assertIn("symbolic link", "\n".join(status["issues"]))
        self.libraries.select("office")
        self.assertEqual(addresses(self.libraries.active), ["office/rate-analysis", "shared/rate-analysis"])
        self.assertEqual(len(self.libraries.active.list_resources()), 2)


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
        self.assertEqual(state["program_settings"]["estimation_skill_library"], "generic")
        self.assertEqual([s["skill"] for s in state["skills"]], [name.split("/")[1] for name in GENERIC + SHARED])
        self.assertEqual(
            state["skills"][0]["read"], "describe_source section=gestimator://skills/generic/civil-takeoff"
        )

    def test_describe_source_reads_skills_and_references_without_a_project(self):
        with self.assertRaises(ToolError):
            execute(self.s, "describe_source", dict(section="skill:in/civil-measurement-estimation"))
        self.s.call("mcp.enable", dict(enabled=False, estimation_skill_library="in"))
        listing = execute(self.s, "describe_source", dict(section="skills"))["data"]["skills"]
        self.assertEqual([s["skill"] for s in listing], [name.split("/")[1] for name in IN + SHARED])
        self.assertIn("references/masonry.md", [r["path"] for r in listing[0]["references"]])
        skill = execute(self.s, "describe_source", dict(section="skill:in/civil-measurement-estimation"))["data"]
        self.assertIn("name: civil-measurement-estimation", skill["text"])
        self.assertIn(
            "gestimator://skills/in/civil-measurement-estimation/references/masonry.md",
            [r["section"] for r in skill["references"]],
        )
        for section in (
            "skill:in/civil-measurement-estimation/references/masonry.md",
            "gestimator://skills/in/civil-measurement-estimation/references/masonry.md",
        ):
            data = execute(self.s, "describe_source", dict(section=section))["data"]
            self.assertIn("IS 1200 (Part 3)", data["text"])
            self.assertNotIn("references", data)
        for section in ("skill:nope", "skill:../x", "gestimator://skills/in/civil-measurement-estimation/../../x.md"):
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
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.user = Path(directory.name) / "skills"
        directory_patch = patch.object(mcp_skills, "user_directory", return_value=self.user)
        directory_patch.start()
        self.addCleanup(directory_patch.stop)
        super().setUp()

    def rpc(self, method, params=None):
        status, message = self.http(message=dict(jsonrpc="2.0", id=9, method=method, params=params or {}))
        self.assertEqual(status, 200)
        return message

    def test_listing_and_reading_without_a_project_in_read_only_mode(self):
        self.start()
        self.assertEqual(self.runtime.call("mcp.status")["access"], "read")
        self.assertFalse(self.tool("get_state")["structuredContent"]["data"]["project_open"])
        initialized = self.rpc(
            "initialize", dict(protocolVersion="2025-11-25", capabilities={}, clientInfo=dict(name="test", version="1"))
        )["result"]
        self.assertEqual(initialized["capabilities"]["resources"], dict(listChanged=False))
        self.assertIn("gestimator://skills/", initialized["instructions"])
        self.assertLess(len(INSTRUCTIONS.split()), 230)

        def resources():
            return self.rpc("resources/list")["result"]["resources"]

        self.assertIn(mcp_skills.SCHEME + GENERIC[0], [resource["uri"] for resource in resources()])
        with self.assertRaises(ValueError):
            self.runtime.call("mcp.enable", dict(enabled=True, estimation_skill_library="../invalid"))
        self.assertIn(mcp_skills.SCHEME + GENERIC[0], [resource["uri"] for resource in resources()])
        self.runtime.call("mcp.enable", dict(enabled=True, estimation_skill_library="in"))
        self.assertEqual(
            self.tool("get_state")["structuredContent"]["data"]["program_settings"]["estimation_skill_library"], "in"
        )
        self.assertEqual(
            self.rpc("resources/read", dict(uri="gestimator://skills/generic/civil-takeoff"))["error"]["code"], -32002
        )
        self.assertIn(mcp_skills.SCHEME + IN[0], [resource["uri"] for resource in resources()])
        self.assertEqual(self.rpc("resources/templates/list")["result"], dict(resourceTemplates=[]))
        for name in IN + SHARED:
            contents = self.rpc("resources/read", dict(uri="gestimator://skills/" + name))["result"]["contents"]
            self.assertEqual(contents[0]["uri"], "gestimator://skills/" + name)
            self.assertEqual(contents[0]["mimeType"], "text/markdown")
            self.assertIn(f"name: {name.split('/')[1]}", contents[0]["text"])
        reference = "gestimator://skills/in/civil-measurement-estimation/references/masonry.md"
        self.assertIn(
            "IS 1200 (Part 3)", self.rpc("resources/read", dict(uri=reference))["result"]["contents"][0]["text"]
        )
        self.assertEqual(self.runtime.call("mcp.status")["last_activity"], "Resource: " + reference)
        self.assertFalse(self.tool("get_state")["structuredContent"]["data"]["project_open"])

    def test_live_refresh_serves_user_library_in_both_discovery_paths(self):
        self.start()
        self.runtime.call("mcp.enable", dict(enabled=True, estimation_skill_library="office"))
        package = install(self.user)
        self.assertEqual(
            self.tool("describe_source", {"section": "skills"})["structuredContent"]["data"]["library"], "generic"
        )
        self.assertEqual(self.runtime.call("mcp.refresh_skill_libraries")["active_library"], "office")
        uri = mcp_skills.SCHEME + "office/rate-analysis"
        resources = self.rpc("resources/list")["result"]["resources"]
        self.assertEqual([resource["uri"] for resource in resources], [uri, mcp_skills.SCHEME + SHARED[0]])
        from_tool = self.tool("describe_source", {"section": uri})["structuredContent"]["data"]
        from_resource = self.rpc("resources/read", {"uri": uri})["result"]["contents"][0]
        self.assertEqual(from_tool["text"], from_resource["text"])
        self.assertIn("Office workflow", from_resource["text"])
        (package / "SKILL.md").unlink()
        self.assertEqual(self.runtime.call("mcp.refresh_skill_libraries")["active_library"], "generic")
        self.assertEqual(self.rpc("resources/read", {"uri": uri})["error"]["code"], -32002)
        self.assertTrue(self.runtime.call("mcp.status")["running"])

    def test_invalid_reads_return_protocol_errors(self):
        self.start()
        missing = self.rpc("resources/read", dict(uri="gestimator://skills/../../etc/passwd"))["error"]
        self.assertEqual((missing["code"], missing["data"]["uri"]), (-32002, "gestimator://skills/../../etc/passwd"))
        self.assertEqual(self.rpc("resources/read", dict(uri="gestimator://skills/nope"))["error"]["code"], -32002)
        self.assertEqual(self.rpc("resources/read", {})["error"]["code"], -32602)
        self.assertEqual(self.rpc("resources/read", dict(uri=["x"]))["error"]["code"], -32602)
        self.assertEqual(
            self.http(
                message=dict(jsonrpc="2.0", id=1, method="resources/list"), headers={"Authorization": "Bearer wrong"}
            )[0],
            401,
        )


if __name__ == "__main__":
    unittest.main()
