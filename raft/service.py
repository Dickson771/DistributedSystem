"""gRPC server glue for the Raft node."""
from __future__ import annotations

import logging
from concurrent import futures
from typing import Optional

import grpc

from . import raft_pb2, raft_pb2_grpc
from .node import PeerInfo, RaftNode

LOGGER = logging.getLogger("raft.server")


class RaftServicer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node: RaftNode) -> None:
        self.node = node

    def AppendEntries(self, request, context):  # noqa: N802 (gRPC)
        LOGGER.info(
            "RPC AppendEntries from %s on %s with %s entries", request.leader_id, self.node.node_id, len(request.entries)
        )
        return self.node.on_append_entries(request)

    def RequestVote(self, request, context):  # noqa: N802
        LOGGER.info("RPC RequestVote from %s on %s", request.candidate_id, self.node.node_id)
        return self.node.on_request_vote(request)

    def ClientCommand(self, request, context):  # noqa: N802
        LOGGER.info("RPC ClientCommand on %s", self.node.node_id)
        return self.node.process_client_command(request.payload)


class RaftServer:
    """Wraps the grpc.Server lifecycle."""

    def __init__(self, node: RaftNode, max_workers: int = 8) -> None:
        self.node = node
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        raft_pb2_grpc.add_RaftServiceServicer_to_server(RaftServicer(node), self._server)
        self._server.add_insecure_port(node.grpc_address)

    def start(self) -> None:
        LOGGER.info("starting gRPC server on %s", self.node.grpc_address)
        self._server.start()

    def stop(self, grace: Optional[float] = None) -> None:
        LOGGER.info("stopping gRPC server on %s", self.node.grpc_address)
        self._server.stop(grace)
        self.node.shutdown()


def build_node(config: dict) -> RaftNode:
    peers = [PeerInfo(peer["node_id"], peer["grpc"], peer["http"]) for peer in config["peers"]]
    node = RaftNode(
        node_id=config["node_id"],
        grpc_address=config["grpc"],
        http_address=config["http"],
        peers=peers,
    )
    node.current_term = config.get("term", 0)
    if config.get("leader", False):
        node.become_leader()
    return node
