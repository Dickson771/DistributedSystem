"""HTTP shim that exposes a very small client API per node."""
from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict

from .node import NotLeaderError, RaftNode

LOGGER = logging.getLogger("raft.http")


class ClientRequestHandler(BaseHTTPRequestHandler):
    server: "RaftHTTPServer"  # type: ignore[assignment]

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        if self.path != "/client":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        LOGGER.info("HTTP request on %s", self.server.node.node_id)
        try:
            result = self.server.node.handle_client_payload(payload)
            body = {
                "status": result["status"],
                "log_index": result["log_index"],
                "commit_index": result["commit_index"],
                "leader": self.server.node.node_id,
            }
            self._write_response(body)
        except NotLeaderError:
            forward = self._forward(payload)
            self._write_response(forward)

    def _forward(self, payload: Dict[str, str]) -> Dict[str, str]:
        try:
            LOGGER.info("forwarding HTTP request to leader from %s", self.server.node.node_id)
            data = self.server.node.forward_http(payload)
            data.setdefault("forwarded", True)
            return data
        except Exception as exc:  # pragma: no cover - network errors
            return {"status": "error", "message": str(exc)}

    def _write_response(self, payload: Dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 (http.server API)
        LOGGER.debug("HTTP: " + format, *args)


class RaftHTTPServer(ThreadingHTTPServer):
    def __init__(self, addr: str, node: RaftNode) -> None:
        host, port_str = addr.split(":")
        super().__init__((host, int(port_str)), ClientRequestHandler)
        self.node = node


def start_http_server(node: RaftNode) -> RaftHTTPServer:
    server = RaftHTTPServer(node.http_address, node)
    LOGGER.info("client API for %s listening on %s", node.node_id, node.http_address)
    return server
