"""Utility script to launch a Raft node with both gRPC and HTTP endpoints."""
from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
from pathlib import Path

from .client_api import start_http_server
from .service import RaftServer, build_node

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s - %(message)s")
LOGGER = logging.getLogger("raft.runner")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Raft node for the demo cluster")
    parser.add_argument("config", type=Path, help="Path to node JSON config")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    node = build_node(config)
    grpc_server = RaftServer(node)
    http_server = start_http_server(node)

    grpc_server.start()

    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    stop_event = threading.Event()

    def _stop(*_):
        LOGGER.info("Stopping node %s", node.node_id)
        stop_event.set()
        http_server.shutdown()
        grpc_server.stop(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    stop_event.wait()


if __name__ == "__main__":
    main()
