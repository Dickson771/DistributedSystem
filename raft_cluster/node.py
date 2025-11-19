"""Minimal Raft node with follower/candidate/leader states."""

from __future__ import annotations

import argparse
import asyncio
import os
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import grpc

import raft_pb2
import raft_pb2_grpc


@dataclass
class PeerConfig:
    """Represents a remote Raft peer."""

    address: str


class RaftNode(raft_pb2_grpc.RaftServicer):
    """Implements the Raft RPCs and manages the node state machine."""

    def __init__(
        self,
        node_id: int,
        peers: Iterable[str],
        port: int,
        *,
        election_timeout_min: float = 1.5,
        election_timeout_max: float = 3.0,
        heartbeat_interval: float = 0.5,
    ) -> None:
        self.node_id = node_id
        self.port = port
        self.peers: List[PeerConfig] = [PeerConfig(address=p) for p in peers]
        self.cluster_size = len(self.peers) + 1
        self.majority = self.cluster_size // 2 + 1

        self.current_term = 0
        self.voted_for: Optional[int] = None
        self.state = "follower"
        self.votes_received: set[str] = set()

        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval

        self.election_reset_event = asyncio.Event()
        self.rpc_clients: Dict[str, raft_pb2_grpc.RaftStub] = {}
        self.rpc_channels: Dict[str, grpc.aio.Channel] = {}

    # ------------------------------------------------------------------ RPCs
    async def RequestVote(
        self, request: raft_pb2.RequestVoteRequest, context: grpc.aio.ServicerContext
    ) -> raft_pb2.RequestVoteResponse:
        if request.term < self.current_term:
            return raft_pb2.RequestVoteResponse(term=self.current_term, voteGranted=False)

        if request.term > self.current_term:
            print(f"Node {self.node_id} observed new term {request.term} from {request.candidateId}")
            await self._become_follower(request.term)

        vote_granted = False
        if self.voted_for in (None, request.candidateId):
            self.voted_for = request.candidateId
            vote_granted = True
            self._reset_election_timer()
            print(
                f"Node {self.node_id} (term {self.current_term}) votes for candidate {request.candidateId}"
            )

        return raft_pb2.RequestVoteResponse(term=self.current_term, voteGranted=vote_granted)

    async def AppendEntries(
        self, request: raft_pb2.AppendEntriesRequest, context: grpc.aio.ServicerContext
    ) -> raft_pb2.AppendEntriesResponse:
        if request.term < self.current_term:
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)

        if request.term >= self.current_term:
            if request.term > self.current_term or self.state != "follower":
                print(f"Node {self.node_id} following leader {request.leaderId} for term {request.term}")
                await self._become_follower(request.term)
            self._reset_election_timer()

        print(
            f"Node {self.node_id} received heartbeat from leader {request.leaderId} (term {request.term})"
        )
        return raft_pb2.AppendEntriesResponse(term=self.current_term, success=True)

    # ----------------------------------------------------------------- helpers
    async def _become_follower(self, term: int) -> None:
        self.current_term = term
        self.state = "follower"
        self.voted_for = None
        self.votes_received.clear()
        self._reset_election_timer()

    def _reset_election_timer(self) -> None:
        if not self.election_reset_event.is_set():
            self.election_reset_event.set()

    async def start(self) -> None:
        server = grpc.aio.server()
        raft_pb2_grpc.add_RaftServicer_to_server(self, server)
        server.add_insecure_port(f"[::]:{self.port}")
        await server.start()

        print(
            f"Node {self.node_id} started as follower on port {self.port} with peers {[p.address for p in self.peers]}"
        )

        await asyncio.gather(
            self._run_election_timer(),
            self._run_heartbeat_loop(),
            server.wait_for_termination(),
        )

    async def _run_election_timer(self) -> None:
        while True:
            timeout = random.uniform(self.election_timeout_min, self.election_timeout_max)
            try:
                await asyncio.wait_for(self.election_reset_event.wait(), timeout)
                self.election_reset_event.clear()
            except asyncio.TimeoutError:
                await self._start_election()

    async def _start_election(self) -> None:
        self.state = "candidate"
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes_received = {str(self.node_id)}
        self._reset_election_timer()

        print(f"Node {self.node_id} starting election for term {self.current_term}")

        await self._broadcast_request_vote()

    async def _broadcast_request_vote(self) -> None:
        if not self.peers:
            # Single node cluster: immediately become leader
            self.state = "leader"
            print(f"Node {self.node_id} is the only node and becomes leader for term {self.current_term}")
            return

        tasks = [self._send_request_vote(peer.address) for peer in self.peers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        granted_votes = sum(1 for result in results if result is True)
        print(
            f"Node {self.node_id} collected {len(self.votes_received)} votes ({granted_votes} new) in term {self.current_term}"
        )

        if self.state == "candidate" and len(self.votes_received) >= self.majority:
            self.state = "leader"
            print(f"Node {self.node_id} became leader for term {self.current_term}")
            self._reset_election_timer()

    async def _send_request_vote(self, peer_address: str) -> bool:
        stub = await self._get_peer_stub(peer_address)
        request = raft_pb2.RequestVoteRequest(
            term=self.current_term,
            candidateId=self.node_id,
            lastLogIndex=0,
            lastLogTerm=0,
        )
        print(
            f"Node {self.node_id} sending RequestVote(term={self.current_term}) to {peer_address}"
        )
        try:
            response = await stub.RequestVote(request, timeout=2)
        except grpc.aio.AioRpcError as exc:
            print(f"Node {self.node_id} failed RequestVote to {peer_address}: {exc}")
            return False

        if response.term > self.current_term:
            print(
                f"Node {self.node_id} stepping down due to higher term {response.term} from {peer_address}"
            )
            await self._become_follower(response.term)
            return False

        if response.voteGranted:
            # Use the peer address as a stand-in for its vote so we don't double count
            self.votes_received.add(str(self.node_id))
            self.votes_received.add(peer_address)
            return True

        return False

    async def _run_heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            if self.state == "leader":
                await self._broadcast_append_entries()

    async def _broadcast_append_entries(self) -> None:
        tasks = [self._send_append_entries(peer.address) for peer in self.peers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_append_entries(self, peer_address: str) -> None:
        stub = await self._get_peer_stub(peer_address)
        request = raft_pb2.AppendEntriesRequest(
            term=self.current_term,
            leaderId=self.node_id,
            prevLogIndex=0,
            prevLogTerm=0,
            leaderCommit=0,
        )
        print(
            f"Node {self.node_id} sending heartbeat AppendEntries(term={self.current_term}) to {peer_address}"
        )
        try:
            response = await stub.AppendEntries(request, timeout=2)
        except grpc.aio.AioRpcError as exc:
            print(f"Node {self.node_id} failed AppendEntries to {peer_address}: {exc}")
            return

        if response.term > self.current_term:
            print(
                f"Node {self.node_id} observed higher term {response.term} while leader; becoming follower"
            )
            await self._become_follower(response.term)

    async def _get_peer_stub(self, peer_address: str) -> raft_pb2_grpc.RaftStub:
        if peer_address not in self.rpc_clients:
            channel = grpc.aio.insecure_channel(peer_address)
            self.rpc_channels[peer_address] = channel
            self.rpc_clients[peer_address] = raft_pb2_grpc.RaftStub(channel)
        return self.rpc_clients[peer_address]


def parse_peers(peer_argument: str) -> List[str]:
    peers = []
    for raw_entry in peer_argument.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            entry = f"{entry}:50051"
        peers.append(entry)
    return peers


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Raft node")
    parser.add_argument("--node-id", type=int, default=int(os.environ.get("RAFT_NODE_ID", "1")))
    parser.add_argument("--port", type=int, default=int(os.environ.get("RAFT_PORT", "50051")))
    parser.add_argument(
        "--peers",
        type=str,
        default=os.environ.get("RAFT_PEERS", ""),
        help="Comma separated list of host:port peers",
    )
    parser.add_argument(
        "--election-timeout-min",
        type=float,
        default=float(os.environ.get("RAFT_ELECTION_TIMEOUT_MIN", "1.5")),
    )
    parser.add_argument(
        "--election-timeout-max",
        type=float,
        default=float(os.environ.get("RAFT_ELECTION_TIMEOUT_MAX", "3.0")),
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=float(os.environ.get("RAFT_HEARTBEAT_INTERVAL", "0.5")),
    )
    return parser


async def async_main(args: argparse.Namespace) -> None:
    peers = parse_peers(args.peers)
    node = RaftNode(
        node_id=args.node_id,
        peers=peers,
        port=args.port,
        election_timeout_min=args.election_timeout_min,
        election_timeout_max=args.election_timeout_max,
        heartbeat_interval=args.heartbeat_interval,
    )
    await node.start()


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("Node interrupted; shutting down")


if __name__ == "__main__":
    main()
