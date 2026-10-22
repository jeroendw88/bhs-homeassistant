"""Run: python -m unittest discover -s tests -v (no HA instance required)."""
import asyncio
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "bhs"
# Loading the pure discovery and API modules without importing HA's integration
# entrypoint avoids requiring a full Home Assistant installation for regression tests.
for name, path in (("custom_components", ROOT / "custom_components"),
                   ("custom_components.bhs", PACKAGE)):
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(path)]
    sys.modules.setdefault(name, pkg)

registry = importlib.import_module("custom_components.bhs.member_registry")
sdim = importlib.import_module("custom_components.bhs.sdim")
rest = importlib.import_module("custom_components.bhs.rest_api")


def member(mid, typ, group, address, version, name):
    return dict(memberID=mid, memberType=typ, group=group, address=address,
                version=version, name=name)


class MemberTests(unittest.TestCase):
    def test_legacy_and_new_relay_roles(self):
        original = member("one", 1, 2, 3, "RLM_4", "VER_Test")
        generic = member("two", 1, 7, 4, "RLM_4", "External pump")
        self.assertEqual(registry.resolve_role(original, {}), registry.ROLE_LIGHT)
        self.assertEqual(registry.resolve_role(generic, {}), registry.ROLE_SWITCH)
        self.assertEqual(registry.resolve_role(original, {"one": "disabled"}), "disabled")

    def test_cover_direction_mapping_not_name_based(self):
        a = member("low", 20, 3, 3, "RLM_4", "Direction X")
        b = member("high", 20, 3, 4, "RLM_4", "Direction Y")
        self.assertEqual(registry.cover_pairs([a, b]), [])
        self.assertEqual([(up["memberID"], down["memberID"]) for up, down in
                          registry.cover_pairs([a, b], {"low": "high"})], [("high", "low")])
        self.assertEqual(registry.cover_pairs([a, b], {"low": "disabled"}), [])

    def test_sdim_role_names_and_duplicates(self):
        scene = member("scene", 19, 12, 221, "SDim", "Evening")
        reset = member("reset", 19, 12, 219, "SDim", "Something Else")
        record = member("record", 19, 12, 229, "SDim", "ABC")
        self.assertEqual(sdim.sdim_role(scene), "scene")
        self.assertEqual(sdim.sdim_role(reset), "group_reset")
        self.assertEqual(sdim.sdim_role(record), "record_scene")
        duplicate = member("dup", 19, 12, 221, "SDim", "Duplicate")
        validated = sdim.validated_sdim_members([scene, reset, record, duplicate])
        self.assertNotIn((12, 221), validated)
        self.assertEqual(validated[(12, 219)]["memberID"], "reset")

    def test_package_versions_match(self):
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        constants = importlib.import_module("custom_components.bhs.const")
        self.assertEqual(manifest["version"], constants.INTEGRATION_VERSION)


class ExportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api = rest.BHSRestApi(None, "localhost", 10014,
                                  "123e4567-e89b-42d3-a456-426614174000")
        self.dim = member("kitchen-dim", 2, 9, 7, "DIM1K_15", "Kitchen unnamed")
        self.reserve = member("reserve-dim", 2, 9, 8, "DIM1K_15", "Reserve")
        self.reset = member("group-reset", 19, 9, 219, "SDim", "Any Name")
        self.scene = member("scene", 19, 9, 221, "SDim", "Movie")
        self.record = member("record", 19, 9, 229, "SDim", "Record")
        self.api._request = AsyncMock(side_effect=self.request)
        self.duplicate = False

    async def request(self, method, path, body=None):
        if path == "/members/getMembers":
            return {"members": [self.dim, self.reserve, self.reset, self.scene, self.record]}
        if path == "/exports/list":
            return {"exports": [{"iD": 2, "allowed": True}]}
        if path == "/exports/content":
            actions = [{"actionID": "DATAW", "function": 224, "register": 1,
                        "flank": 1, "lsb": 10, "msb": 224},
                       {"actionID": "kitchen-dim", "function": 96, "register": 2,
                        "flank": 0, "lsb": 7, "msb": 137}]
            button = {"caption": "Kitchen", "actions": actions}
            return {"rooms": [{"buttons": [button, button] if self.duplicate else [button]}]}
        raise AssertionError(f"unexpected API request {path}")

    async def test_validated_export_across_groups(self):
        await self.api.get_members()
        self.assertTrue(self.api.supports_brightness("kitchen-dim"))
        self.assertFalse(self.api.supports_brightness("reserve-dim"))
        self.assertEqual(self.api._brightness_actions["kitchen-dim"],
                         (2, "Kitchen", 7, 137))
        self.assertIn("kitchen-dim", self.api._allowed_dimmer_ids)
        self.assertNotIn("reserve-dim", self.api._allowed_dimmer_ids)
        self.assertIn("scene", self.api._allowed_scene_ids)
        self.assertNotIn("record", self.api._allowed_scene_ids)
        self.assertNotIn("kitchen-dim", self.api._allowed_start_dim_ids)

    async def test_duplicate_export_is_blocked(self):
        self.duplicate = True
        await self.api.get_members()
        self.assertFalse(self.api.supports_brightness("kitchen-dim"))


if __name__ == "__main__":
    unittest.main()
