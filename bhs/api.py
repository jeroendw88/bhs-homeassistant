"""Async client for the BHS DataSnap REST API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession

from .exceptions import BHSApiError, BHSConnectionError


class BHSApi:
    """Small async wrapper around TServerMethodsBHS."""

    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        """Initialize the API client."""
        self._session = session
        self._host = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
        self._port = port
        self._base_url = (
            f"http://{self._host}:{self._port}/datasnap/rest/TServerMethodsBHS"
        )

    @property
    def host(self) -> str:
        """Return the configured BHS host."""
        return self._host

    @property
    def port(self) -> int:
        """Return the configured BHS HTTP port."""
        return self._port

    async def _get(self, method: str, *params: object) -> Any:
        """Call a DataSnap REST method and return decoded JSON."""
        path = "/".join(
            [quote(method, safe=""), *(quote(str(param), safe="") for param in params)]
        )
        url = f"{self._base_url}/{path}"

        try:
            async with self._session.get(url, timeout=10) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise BHSConnectionError(f"Unable to communicate with BHS at {self._host}:{self._port}") from err

        if isinstance(payload, dict) and "error" in payload:
            raise BHSApiError(str(payload["error"]))

        return payload

    async def get_bhs_info(self) -> dict[str, Any]:
        """Return controller information."""
        payload = await self._get("getBHSInfo")
        if not isinstance(payload, dict):
            raise BHSApiError("Unexpected getBHSInfo response")
        return payload

    async def get_members(self) -> list[dict[str, Any]]:
        """Return all configured BHS members."""
        payload = await self._get("getMembers")
        if not isinstance(payload, dict) or not isinstance(payload.get("members"), list):
            raise BHSApiError("Unexpected getMembers response")
        return payload["members"]

    async def get_member_states(self) -> dict[str, str]:
        """Return memberID -> state for all members."""
        payload = await self._get("getMemberState")
        states: dict[str, str] = {}

        if isinstance(payload, dict) and isinstance(payload.get("membersState"), list):
            for item in payload["membersState"]:
                if not isinstance(item, dict):
                    continue
                member_id = item.get("memberID")
                status = item.get("status")
                if member_id and isinstance(status, str):
                    states[str(member_id)] = status
            return states

        # Be liberal in case another BHS server returns a direct mapping.
        if isinstance(payload, dict):
            for member_id, status in payload.items():
                if isinstance(status, str):
                    states[str(member_id)] = status
            if states:
                return states

        raise BHSApiError("Unexpected getMemberState response")

    async def get_member_state(self, member_id: str) -> str | None:
        """Return the state for one member."""
        payload = await self._get("getMemberStateByMemberID", member_id)
        if isinstance(payload, dict):
            value = payload.get(member_id)
            return value if isinstance(value, str) else None
        raise BHSApiError("Unexpected getMemberStateByMemberID response")

    async def command_member(self, member_id: str, function: str) -> Any:
        """Send Set/Reset/Toggle/Timer/Dimmer to a member."""
        return await self._get("commandMemberID", member_id, function)
