"""BHS REST v2 API client (unsecured mode, including tested group-5 DIM1K start/stop)."""
from __future__ import annotations

from typing import Any
from uuid import UUID
from aiohttp import ClientError, ClientSession
from .exceptions import BHSApiError, BHSConnectionError


class BHSRestApi:
    """Use a previously registered device UUID; never register automatically."""

    def __init__(self, session: ClientSession, host: str, port: int, device_id: str) -> None:
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
        # Only explicitly known VER_* RLM_4 relays are enabled for REST writes.
        # In particular, DIM_* members, shutters, software members and alarm
        # outputs must remain blocked until their behavior has been tested.
        self._allowed_light_ids = {
            str(m["memberID"]) for m in valid_members
            if m.get("memberType") == 1
            and str(m.get("version", "")).casefold() == "rlm_4"
            and str(m.get("name", "")).startswith("VER_")
            and m.get("group") == 2
        }
        self._allowed_socket_ids = {
            str(m["memberID"]) for m in valid_members
            if m.get("memberType") == 1
            and str(m.get("version", "")).casefold() == "rlm_4"
            and str(m.get("name", "")).startswith("SK_")
            and m.get("group") == 2
        }
        # Only complete, adjacent group-3 RLM_4 cover pairs are writable.
        # A missing direction relay keeps the entire pair blocked.
        candidates = {
            int(m["address"]): m for m in valid_members
            if m.get("memberType") == 20
            and m.get("group") == 3
            and str(m.get("version", "")).casefold() == "rlm_4"
            and isinstance(m.get("address"), int)
        }
        self._allowed_cover_ids = set()
        for odd_address in range(1, 256, 2):
            first, second = candidates.get(odd_address), candidates.get(odd_address + 1)
            if first and second:
                first_name = str(first.get("name", "")).upper()
                second_name = str(second.get("name", "")).upper()
                if first_name.endswith("_OP") and second_name.endswith("_NEER"):
                    self._allowed_cover_ids.update((str(first["memberID"]), str(second["memberID"])))
        # DIM1K channels: only full-on Set and off Reset, no cyclic dimming.
        self._allowed_dimmer_ids = {
            str(m["memberID"]) for m in valid_members
            if m.get("memberType") == 2
            and str(m.get("version", "")).casefold() == "dim1k_15"
            and str(m.get("name", "")).startswith("DIM_")
            and m.get("group") == 5
        }
        # Cyclic dimming has been physically verified only on group 5.
        # Require an exactly identified group-5 Stop Dim member; otherwise
        # block starts to avoid leaving a dimming operation running.
        stop_members = [
            m for m in valid_members
            if m.get("group") == 5
            and m.get("address") == 220
            and m.get("memberType") == 19
            and str(m.get("version", "")).casefold() == "sdim"
            and str(m.get("name", "")).strip().casefold() == "stop dim"
        ]
        self._allowed_stop_dim_ids = (
            {str(stop_members[0]["memberID"])} if len(stop_members) == 1 else set()
        )
        self._allowed_start_dim_ids = (
            set(self._allowed_dimmer_ids) if self._allowed_stop_dim_ids else set()
        )
        # Scene switches from groups 5 and 6 already use the legacy 'dimmer'
        # function. Allow scene activation and group reset, never recording,
        # physical cyclic dimming or other group control functions.
        self._allowed_scene_ids = set()
        self._allowed_scene_reset_ids = set()
        for m in valid_members:
            if (m.get("memberType") != 19
                or str(m.get("version", "")).casefold() != "sdim"
                or m.get("group") not in (5, 6)):
                continue
            name = str(m.get("name") or "").strip().casefold()
            if name == "groepsreset dim":
                self._allowed_scene_reset_ids.add(str(m["memberID"]))
            elif (name not in ("stop dim", "groepssturing dim")
                  and "record" not in name):
                self._allowed_scene_ids.add(str(m["memberID"]))
        # Conservative SoftM rollout. Explicitly exclude whole-house, alarm,
        # step, and scene-like SoftM members. Other SoftM remain read-only.
        # This check uses discovery metadata, never a user-supplied name.
        self._allowed_soft_ids = {
            str(m["memberID"]) for m in valid_members
            if m.get("group") == 10
            and m.get("memberType") == 4
            and str(m.get("version", "")).casefold() == "softm"
            and str(m.get("name", "")).casefold().startswith("bwm_")
            and str(m.get("name", "")).casefold().endswith(("_bypass", "_down"))
        }
        return valid_members

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
            or (member_id in (self._allowed_start_dim_ids | self._allowed_stop_dim_ids)
                and function == "dimmer")
        )
        if not permitted:
            raise BHSApiError(
                "REST command blocked: supported operations are relay/DIM1K "
                "Set/Reset, approved SDim scenes, group-5 Start/Stop Dimmer, and approved BWM SoftM controls only"
            )
        return await self._request(
            "POST", "/members/command",
            {"memberID": member_id, "function": function},
        )
