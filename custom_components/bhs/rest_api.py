"""BHS REST API client with validated, export-driven DIM1K brightness commands."""
from __future__ import annotations

from typing import Any
import asyncio
from uuid import UUID
from aiohttp import ClientError, ClientSession
from .exceptions import BHSApiError, BHSConnectionError
from .sdim import sdim_role, validated_sdim_members
from .member_registry import (is_relay, is_dimmer, is_exu, is_soft,
    resolve_role, cover_pairs, ROLE_LIGHT, ROLE_SWITCH, ROLE_EXU, ROLE_SOFT)


class BHSRestApi:
    """Use a previously registered device UUID; never register automatically."""

    def __init__(self, session: ClientSession, host: str, port: int, device_id: str,
                 dimmer_export_id: int = 2, exu_export_id: int = 7,
                 member_roles: dict[str, str] | None = None,
                 cover_directions: dict[str, str] | None = None) -> None:
        self.member_roles = member_roles or {}
        self.cover_directions = cover_directions or {}
        self._session = session
        self._host = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
        self._port = port
        self._device_id = str(UUID(device_id.strip()))
        if UUID(self._device_id).version != 4:
            raise BHSApiError("Device ID must be a UUID v4")
        self._base_url = f"http://{self._host}:{self._port}/api"
        self._allowed_light_ids: set[str] = set()
        self._allowed_socket_ids: set[str] = set()
        self._allowed_cover_ids: set[str] = set()
        self._allowed_dimmer_ids: set[str] = set()
        self._allowed_scene_ids: set[str] = set()
        self._allowed_scene_reset_ids: set[str] = set()
        self._allowed_start_dim_ids: set[str] = set()
        self._allowed_stop_dim_ids: set[str] = set()
        self._allowed_soft_ids: set[str] = set()
        self._allowed_exu_ids: set[str] = set()
        self.dimmer_export_id = dimmer_export_id
        self.exu_export_id = exu_export_id  # Reserved for dedicated EXU export APIs.
        self._brightness_actions: dict[str, tuple[int, str, int, int]] = {}
        self._brightness_lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def read_only(self) -> bool:
        return False

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        headers = {"x-device-id": self._device_id}
        if method == "POST":
            headers["Content-Type"] = "application/json"
        try:
            async with self._session.request(method, f"{self._base_url}{path}",
                    headers=headers, json=body if method == "POST" else None,
                    timeout=15) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    message = payload.get("error", "request failed") if isinstance(payload, dict) else "request failed"
                    raise BHSApiError(f"BHS REST HTTP {response.status}: {message}")
        except (ClientError, TimeoutError, ValueError) as err:
            raise BHSConnectionError("Unable to communicate with BHS REST API") from err
        if not isinstance(payload, dict):
            raise BHSApiError("Unexpected REST response")
        if "response" in payload:
            raise BHSApiError("Encrypted REST response unsupported in this preview")
        if "error" in payload:
            raise BHSApiError(str(payload["error"]))
        return payload

    async def check_security(self) -> None:
        result = await self._request("GET", "/bhs/isSecured")
        if result.get("isSecure") is not False:
            raise BHSApiError("This preview supports only isSecure=false")

    async def get_bhs_info(self) -> dict[str, Any]:
        await self.check_security()
        connection = await self._request("GET", "/bhs/connection")
        guid = connection.get("serverGUID")
        if not guid:
            raise BHSApiError("BHS REST connection response missing serverGUID")
        version = await self._request("GET", "/bhs/version")
        return {"serverGUID": guid, "serverVersion": version.get("serverVersion"),
                "apiVersion": version.get("apiVersion"), "apiVersionBuilt": version.get("apiVersionBuilt")}

    async def get_members(self) -> list[dict[str, Any]]:
        payload = await self._request("POST", "/members/getMembers", {})
        members = payload.get("members")
        if not isinstance(members, list):
            raise BHSApiError("Unexpected REST getMembers response")
        valid_members = [m for m in members if isinstance(m, dict) and m.get("memberID")]
        # Discovery is keyed by hardware metadata + explicit member-ID mappings.
        # Legacy classification remains a fallback for existing installations.
        # Unrecognized RLM_4 channels are visible as switches, but writes need
        # either an explicit mapping or the previously supported name/group.
        self._allowed_light_ids = {
            str(m["memberID"]) for m in valid_members
            if is_relay(m) and resolve_role(m, self.member_roles) == ROLE_LIGHT
            and (str(m["memberID"]) in self.member_roles
                 or (m.get("group") == 2 and str(m.get("name") or "").startswith("VER_")))
        }
        self._allowed_socket_ids = {
            str(m["memberID"]) for m in valid_members
            if is_relay(m) and resolve_role(m, self.member_roles) == ROLE_SWITCH
            and (self.member_roles.get(str(m["memberID"])) == ROLE_SWITCH
                 or (m.get("group") == 2 and str(m.get("name") or "").startswith("SK_")))
        }
        # Covers are writable only if the pair is complete and directional
        # mapping has been explicitly confirmed or matches legacy _OP names.
        self._allowed_cover_ids = {
            str(m["memberID"])
            for up, down in cover_pairs(valid_members, self.cover_directions)
            for m in (up, down)
        }
        # Group-5 dimmer on/off commands retain their tested baseline.
        # Other groups gain Set/Reset permission only after export validation.
        self._allowed_dimmer_ids = {
            str(m["memberID"]) for m in valid_members
            if is_dimmer(m) and m.get("group") == 5
        }
        dimmer_members = {
            str(m["memberID"]): m for m in valid_members if is_dimmer(m)
        }
        # Cyclic dimming has been physically verified only on group 5.
        # Require an exactly identified group-5 Stop Dim member; otherwise
        # block starts to avoid leaving a dimming operation running.
        validated_sdim = validated_sdim_members(valid_members)
        self._allowed_stop_dim_ids = {
            str(member["memberID"]) for (group, address), member in validated_sdim.items()
            if address == 220
        }
        # Only group 5 has verified cyclic dimming start behavior.
        self._allowed_start_dim_ids = (
            set(self._allowed_dimmer_ids) if (5, 220) in validated_sdim else set()
        )
        # SDim slots are identified by address, not user-edited names.
        # Recording is NEVER allowed. A scene is enabled only if its group
        # has one unambiguous reset member, matching switch entity creation.
        self._allowed_scene_ids = set()
        self._allowed_scene_reset_ids = set()
        for (group, address), member in validated_sdim.items():
            if sdim_role(member) == "scene" and (group, 219) in validated_sdim:
                self._allowed_scene_ids.add(str(member["memberID"]))
                self._allowed_scene_reset_ids.add(str(validated_sdim[(group, 219)]["memberID"]))
        # Only legacy vetted channels or explicitly opted-in member IDs can
        # receive potentially consequential SoftM / EXU commands.
        self._allowed_soft_ids = {
            str(m["memberID"]) for m in valid_members
            if is_soft(m) and resolve_role(m, self.member_roles) == ROLE_SOFT
        }
        self._allowed_exu_ids = {
            str(m["memberID"]) for m in valid_members
            if is_exu(m) and resolve_role(m, self.member_roles) == ROLE_EXU
        }
        # Find exported DATAW/Timer pairs dynamically. Never derive physical
        # bus bytes from an arbitrary member ID or trust button captions alone.
        self._brightness_actions = {}
        try:
            exports = await self._request("GET", "/exports/list")
            allowed = {
                int(e["iD"]) for e in exports.get("exports", [])
                if isinstance(e, dict) and e.get("allowed") is True
                and isinstance(e.get("iD"), int)
            }
            # Use the configured, authorized dimmer export.
            if self.dimmer_export_id in allowed:
                content = await self._request("POST", "/exports/content", {"exportID": self.dimmer_export_id})
                candidates: dict[str, tuple[int, str, int, int]] = {}
                duplicates: set[str] = set()
                for room in content.get("rooms", []):
                    if not isinstance(room, dict):
                        continue
                    for button in room.get("buttons", []):
                        if not isinstance(button, dict):
                            continue
                        actions = button.get("actions", [])
                        if not isinstance(actions, list) or len(actions) != 2:
                            continue
                        data, timer = actions
                        if not isinstance(data, dict) or not isinstance(timer, dict):
                            continue
                        member_id = str(timer.get("actionID") or "")
                        member = dimmer_members.get(member_id)
                        if member is None:
                            continue
                        # Match a recognized percentage DATAW + targeted TIMER
                        # action, without assuming the dimmer's BHS group or
                        # the TIMER bus MSB. No bus bytes are calculated from IDs.
                        if (data.get("actionID") != "DATAW"
                            or data.get("function") != 224
                            or data.get("register") != 1
                            or data.get("flank") != 1
                            or data.get("msb") != 224
                            or not isinstance(data.get("lsb"), int)
                            or not 0 <= data["lsb"] <= 100
                            or timer.get("register") != 2
                            or timer.get("flank") != 0
                            or timer.get("function") != 96
                            or not isinstance(timer.get("lsb"), int)
                            or timer["lsb"] != member.get("address")
                            or not isinstance(timer.get("msb"), int)
                            or not 0 <= timer["msb"] <= 255):
                            continue
                        # Require a positive target group/address and a named
                        # button from the selected, authorized mobile export.
                        if (not isinstance(member.get("group"), int)
                            or member["group"] < 1
                            or not 1 <= timer["lsb"] <= 255):
                            continue
                        caption = button.get("caption")
                        if not isinstance(caption, str) or not caption.strip():
                            continue
                        if member_id in candidates:
                            duplicates.add(member_id)
                        candidates[member_id] = (
                            self.dimmer_export_id, caption, timer["lsb"], timer["msb"]
                        )
                self._brightness_actions = {
                    key: val for key, val in candidates.items() if key not in duplicates
                }
                # Only export-validated channels beyond group 5 may receive
                # basic Set/Reset. Do not enable cyclic dimming outside group 5.
                self._allowed_dimmer_ids.update(self._brightness_actions)
        except (BHSApiError, ValueError, TypeError, KeyError):
            # Optional feature: existing lights remain functional if the export
            # is missing, inaccessible, or changed.
            self._brightness_actions = {}
        return valid_members

    def supports_brightness(self, member_id: str) -> bool:
        return member_id in self._brightness_actions

    async def set_brightness(self, member_id: str, percent: int) -> None:
        """Apply a validated export DATAW percent and channel TIMER telegram."""
        if member_id not in self._brightness_actions or not 1 <= percent <= 100:
            raise BHSApiError("Brightness command not allowed for this dimmer")
        export_id, name, address, msb = self._brightness_actions[member_id]
        async with self._brightness_lock:
            press = await self._request("POST", "/bus/send", {
                "exportID": export_id, "name": name, "flank": "press",
                "actions": [{"lsb": percent, "msb": 224}],
            })
            if press.get("sent") != 1:
                raise BHSApiError("BHS did not confirm the brightness DATAW send")
            await asyncio.sleep(0.1)
            release = await self._request("POST", "/bus/send", {
                "exportID": export_id, "name": name, "flank": "release",
                "actions": [{"lsb": address, "msb": msb}],
            })
            if release.get("sent") != 1:
                raise BHSApiError("BHS did not confirm the brightness Timer send")

    async def get_member_states(self) -> dict[str, str]:
        payload = await self._request("GET", "/members/getMemberState")
        members = payload.get("members")
        if not isinstance(members, list):
            raise BHSApiError("Unexpected REST getMemberState response")
        return {str(m["memberID"]): m["state"] for m in members
                if isinstance(m, dict) and m.get("memberID") and isinstance(m.get("state"), str)}

    async def get_changes(self) -> dict[str, Any]:
        """Consume this registered device's event queue once per call.

        Never call this API from multiple consumers sharing the same UUID.
        """
        payload = await self._request("GET", "/members/getChanges")
        if not isinstance(payload.get("fresh"), bool) or not isinstance(payload.get("changes"), list):
            raise BHSApiError("Unexpected REST getChanges response")
        return payload

    async def command_member(self, member_id: str, function: str) -> Any:
        """Enforce a per-member allowlist of tested REST command categories."""
        relay_ids = (self._allowed_light_ids | self._allowed_socket_ids
                     | self._allowed_cover_ids | self._allowed_dimmer_ids)
        permitted = (
            (member_id in relay_ids and function in ("set", "reset"))
            or (member_id in (self._allowed_scene_ids | self._allowed_scene_reset_ids)
                and function == "dimmer")
            or (member_id in self._allowed_soft_ids and function in ("set", "reset"))
            or (member_id in self._allowed_exu_ids and function in ("set", "reset"))
            or (member_id in (self._allowed_start_dim_ids | self._allowed_stop_dim_ids)
                and function == "dimmer")
        )
        if not permitted:
            raise BHSApiError(
                "REST command blocked: supported operations are relay/DIM1K "
                "Set/Reset, approved SDim scenes, group-5 Start/Stop Dimmer, approved BWM SoftM controls, and validated EXU modes only"
            )
        return await self._request(
            "POST", "/members/command",
            {"memberID": member_id, "function": function},
        )
