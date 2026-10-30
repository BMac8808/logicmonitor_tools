"""Minimal MCP client for the Streamable HTTP transport, plus a parser for the result
format of the public logicmonitor-api-mcp server.

Only what this app needs: initialize a session, call a tool, close the session.
LogicMonitor credentials are never sent from here; the MCP server holds them
(LM_ACCOUNT / LM_BEARER_TOKEN on the server). The optional ``token`` is the MCP server's
own bearer token (its AUTH_MODE=bearer setting).
"""

from __future__ import annotations

import itertools
import json
import re
from typing import Any

import httpx

from .base import AdapterError

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "se-demo-pov-builder", "version": "0.2.0"}


class MCPError(AdapterError):
    pass


def _sse_messages(body: str) -> list[dict[str, Any]]:
    """Extract JSON-RPC messages from a text/event-stream body."""
    messages, data_lines = [], []
    for line in [*body.splitlines(), ""]:
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif not line.strip() and data_lines:
            try:
                messages.append(json.loads("\n".join(data_lines)))
            except ValueError:
                pass
            data_lines = []
    return messages


class MCPClient:
    def __init__(self, url: str, token: str = "", timeout: float = 30.0,
                 transport: httpx.BaseTransport | None = None):
        self.url = url
        self._token = token
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._session_id: str | None = None
        self._protocol = PROTOCOL_VERSION
        self._ids = itertools.count(1)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
            headers["MCP-Protocol-Version"] = self._protocol
        return headers

    def _send(self, method: str, params: dict[str, Any] | None = None, notify: bool = False) -> dict[str, Any]:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        msg_id = None if notify else next(self._ids)
        if msg_id is not None:
            msg["id"] = msg_id
        try:
            resp = self._client.post(self.url, json=msg, headers=self._headers())
        except httpx.HTTPError as exc:
            raise MCPError(f"Cannot reach MCP server at {self.url}: {exc.__class__.__name__}") from exc
        if resp.status_code in (401, 403):
            raise MCPError(f"MCP server refused the request ({resp.status_code}); check SEPB_MCP_TOKEN")
        if resp.status_code >= 400:
            raise MCPError(f"MCP server returned HTTP {resp.status_code}")
        if session := resp.headers.get("mcp-session-id"):
            self._session_id = session
        if notify:
            return {}
        if resp.headers.get("content-type", "").startswith("text/event-stream"):
            candidates = _sse_messages(resp.text)
        else:
            try:
                body = resp.json()
            except ValueError as exc:
                raise MCPError("MCP server returned a non-JSON response") from exc
            candidates = body if isinstance(body, list) else [body]
        reply = next((m for m in candidates if m.get("id") == msg_id), None)
        if reply is None:
            raise MCPError(f"No response to '{method}' from MCP server")
        if "error" in reply:
            raise MCPError(f"MCP error: {reply['error'].get('message', reply['error'])}")
        return reply.get("result", {})

    def initialize(self) -> dict[str, Any]:
        result = self._send("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO,
        })
        self._protocol = result.get("protocolVersion", PROTOCOL_VERSION)
        self._send("notifications/initialized", notify=True)
        return result

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._session_id is None:
            self.initialize()
        return self._send("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self._session_id:
            try:
                self._client.delete(self.url, headers=self._headers())
            except httpx.HTTPError:
                pass
            self._session_id = None
        self._client.close()


_ITEMS_RE = re.compile(r"^Items \((\d+)(?: of (\d+))?\):")
_PAYLOAD_PREFIX = "Full LogicMonitor payload:"


def parse_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    """Turn a logicmonitor-api-mcp tool result into ``{summary, items, total, format}``.

    The server returns a summary text followed by either the full JSON payload (small
    lists) or a compact Markdown table (larger lists); both are handled.
    """
    texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
    if result.get("isError"):
        raise MCPError(texts[0] if texts else "MCP tool returned an error")
    summary = texts[0] if texts else ""
    for text in texts[1:]:
        if text.startswith(_PAYLOAD_PREFIX):
            try:
                payload = json.loads(text[len(_PAYLOAD_PREFIX):].strip())
            except ValueError:
                break
            items = payload.get("items", []) if isinstance(payload, dict) else []
            total = payload.get("total", len(items)) if isinstance(payload, dict) else len(items)
            return {"summary": summary, "items": items, "total": total, "format": "json"}
        lines = text.splitlines()
        if lines and (m := _ITEMS_RE.match(lines[0])):
            rows = [ln for ln in lines[1:] if ln.startswith("|")]
            if rows:
                header = [h.strip() for h in rows[0].strip("|").split("|")]
                items = [dict(zip(header, (c.strip() for c in r.strip("|").split("|")), strict=False))
                         for r in rows[1:]]
                total = int(m.group(2) or m.group(1))
                return {"summary": summary, "items": items, "total": total, "format": "table"}
    return {"summary": summary, "items": [], "total": None, "format": "text", "text": "\n".join(texts[1:])}
