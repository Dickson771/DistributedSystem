"""Core Raft node implementation used by the demo cluster."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import grpc

from . import raft_pb2, raft_pb2_grpc

LOGGER = logging.getLogger("raft")


@dataclass
class PeerInfo:
    """Connection metadata for a cluster member."""

    node_id: str
    grpc_address: str
    http_address: str


@dataclass
class LogEntry:
    """In-memory representation of a replicated log entry."""

    index: int
    term: int
    command: str


class NotLeaderError(RuntimeError):
    """Raised when a client request hits a non-leader node."""

    def __init__(self, leader_id: Optional[str] = None, leader_http: Optional[str] = None):
        super().__init__("request must be processed by the leader")
        self.leader_id = leader_id
        self.leader_http = leader_http


class RaftNode:
    """Simplified Raft node capable of log replication and client handling."""

    def __init__(
        self,
        node_id: str,
        grpc_address: str,
        http_address: str,
        peers: Iterable[PeerInfo],
    ) -> None:
        self.node_id = node_id
        self.grpc_address = grpc_address
        self.http_address = http_address
        self.peers: Dict[str, PeerInfo] = {peer.node_id: peer for peer in peers}
        if node_id not in self.peers:
            self.peers[node_id] = PeerInfo(node_id=node_id, grpc_address=grpc_address, http_address=http_address)

        # Persistent state
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []

        # Volatile state
        self.commit_index = 0
        self.last_applied = 0

        # Leader state
        self.state = "follower"
        self.leader_id: Optional[str] = None
        self.leader_http_address: Optional[str] = None
        self.next_index: Dict[str, int] = {peer_id: 1 for peer_id in self.peers if peer_id != self.node_id}
        self.match_index: Dict[str, int] = {peer_id: 0 for peer_id in self.peers}
        self.match_index[self.node_id] = 0
        self.pending_operations: List[int] = []

        # State machine results
        self.state_machine: Dict[str, str] = {}
        self._channel_cache: Dict[str, grpc.Channel] = {}
        self._stub_cache: Dict[str, raft_pb2_grpc.RaftServiceStub] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Cluster role helpers
    # ------------------------------------------------------------------
    @property
    def last_log_index(self) -> int:
        return len(self.log)

    @property
    def last_log_term(self) -> int:
        if not self.log:
            return 0
        return self.log[-1].term

    def become_leader(self) -> None:
        with self._lock:
            self.state = "leader"
            self.leader_id = self.node_id
            self.leader_http_address = self.http_address
            self.next_index = {peer_id: self.last_log_index + 1 for peer_id in self.peers if peer_id != self.node_id}
            self.match_index = {peer_id: 0 for peer_id in self.peers}
            self.match_index[self.node_id] = self.last_log_index
            LOGGER.info("%s became leader for term %s", self.node_id, self.current_term)

    # ------------------------------------------------------------------
    # Client handling
    # ------------------------------------------------------------------
    def handle_client_payload(self, payload: Dict[str, str]) -> Dict[str, str]:
        """Process a client request locally or forward to the leader."""

        with self._lock:
            if self.state != "leader":
                raise NotLeaderError(self.leader_id, self.leader_http_address)

            payload_str = json.dumps(payload, sort_keys=True)
            entry = LogEntry(index=self.last_log_index + 1, term=self.current_term, command=payload_str)
            self.log.append(entry)
            self.match_index[self.node_id] = entry.index
            self.pending_operations.append(entry.index)
            LOGGER.info("%s appended client op at index %s", self.node_id, entry.index)

        self.broadcast_append_entries(heartbeat=False)
        applied = self.wait_for_commit(entry.index)
        return {
            "status": "ok" if applied else "pending",
            "log_index": entry.index,
            "commit_index": self.commit_index,
        }

    def wait_for_commit(self, index: int, timeout: float = 2.0) -> bool:
        """Blocks until the given log index is committed or timeout expires."""

        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if self.commit_index >= index:
                    return True
            time.sleep(0.05)
        return False

    # ------------------------------------------------------------------
    # RPC plumbing
    # ------------------------------------------------------------------
    def _stub_for_peer(self, peer_id: str) -> raft_pb2_grpc.RaftServiceStub:
        if peer_id not in self._stub_cache:
            info = self.peers[peer_id]
            channel = grpc.insecure_channel(info.grpc_address)
            self._channel_cache[peer_id] = channel
            self._stub_cache[peer_id] = raft_pb2_grpc.RaftServiceStub(channel)
        return self._stub_cache[peer_id]

    def broadcast_append_entries(self, heartbeat: bool = True) -> None:
        threads = []
        for peer_id in self.peers:
            if peer_id == self.node_id:
                continue
            t = threading.Thread(target=self._send_append_entries, args=(peer_id, heartbeat), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    def _send_append_entries(self, peer_id: str, heartbeat: bool) -> None:
        with self._lock:
            next_idx = self.next_index.get(peer_id, self.last_log_index + 1)
            prev_index = max(0, next_idx - 1)
            prev_term = self.log[prev_index - 1].term if prev_index > 0 and prev_index - 1 < len(self.log) else 0
            entries = []
            if next_idx <= self.last_log_index:
                entries = [self._entry_to_proto(e) for e in self.log[next_idx - 1 :]]
            elif not heartbeat:
                entries = []

            request = raft_pb2.AppendEntriesRequest(
                term=self.current_term,
                leader_id=self.node_id,
                prev_log_index=prev_index,
                prev_log_term=prev_term,
                entries=entries,
                leader_commit=self.commit_index,
                heartbeat=heartbeat and not entries,
                leader_address=self.grpc_address,
                leader_http_address=self.http_address,
            )
        try:
            LOGGER.info("%s -> %s AppendEntries (prev=%s, entries=%s)", self.node_id, peer_id, prev_index, len(entries))
            stub = self._stub_for_peer(peer_id)
            response = stub.AppendEntries(request, timeout=1.0)
            self._on_append_entries_response(peer_id, response)
        except grpc.RpcError as exc:
            LOGGER.warning("append entries to %s failed: %s", peer_id, exc)

    def _on_append_entries_response(self, peer_id: str, response: raft_pb2.AppendEntriesResponse) -> None:
        with self._lock:
            if response.term > self.current_term:
                LOGGER.info("%s discovered higher term %s", self.node_id, response.term)
                self.current_term = response.term
                self.state = "follower"
                self.leader_id = None
                return

            if response.success:
                self.match_index[peer_id] = response.match_index
                self.next_index[peer_id] = response.match_index + 1
                self._update_commit_index()
            else:
                self.next_index[peer_id] = max(1, self.next_index.get(peer_id, 1) - 1)
                LOGGER.debug("%s decrement next index for %s -> %s", self.node_id, peer_id, self.next_index[peer_id])

    def _entry_to_proto(self, entry: LogEntry) -> raft_pb2.LogEntry:
        return raft_pb2.LogEntry(term=entry.term, index=entry.index, command=entry.command)

    # ------------------------------------------------------------------
    # AppendEntries handling
    # ------------------------------------------------------------------
    def on_append_entries(self, request: raft_pb2.AppendEntriesRequest) -> raft_pb2.AppendEntriesResponse:
        with self._lock:
            LOGGER.info("%s received AppendEntries from %s", self.node_id, request.leader_id)
            if request.term < self.current_term:
                return raft_pb2.AppendEntriesResponse(
                    term=self.current_term,
                    success=False,
                    match_index=self.last_log_index,
                    last_log_index=self.last_log_index,
                    message="stale term",
                )

            self.state = "follower"
            self.leader_id = request.leader_id
            self.leader_http_address = request.leader_http_address
            self.current_term = request.term

            if request.prev_log_index > self.last_log_index:
                return raft_pb2.AppendEntriesResponse(
                    term=self.current_term,
                    success=False,
                    match_index=self.last_log_index,
                    last_log_index=self.last_log_index,
                    message="missing log",
                )

            if request.prev_log_index > 0:
                local_term = self.log[request.prev_log_index - 1].term
                if local_term != request.prev_log_term:
                    self.log = self.log[: request.prev_log_index - 1]
                    return raft_pb2.AppendEntriesResponse(
                        term=self.current_term,
                        success=False,
                        match_index=self.last_log_index,
                        last_log_index=self.last_log_index,
                        message="term mismatch",
                    )

            for incoming in request.entries:
                if incoming.index <= self.last_log_index:
                    local = self.log[incoming.index - 1]
                    if local.term != incoming.term:
                        self.log = self.log[: incoming.index - 1]
                        self.log.append(LogEntry(incoming.index, incoming.term, incoming.command))
                else:
                    self.log.append(LogEntry(incoming.index, incoming.term, incoming.command))

            if request.leader_commit > self.commit_index:
                self.commit_index = min(request.leader_commit, self.last_log_index)
                self._apply_committed_entries()

            return raft_pb2.AppendEntriesResponse(
                term=self.current_term,
                success=True,
                match_index=self.last_log_index,
                last_log_index=self.last_log_index,
                message="ok",
            )

    # ------------------------------------------------------------------
    # Vote handling
    # ------------------------------------------------------------------
    def on_request_vote(self, request: raft_pb2.RequestVoteRequest) -> raft_pb2.RequestVoteResponse:
        with self._lock:
            if request.term < self.current_term:
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)

            up_to_date = (request.last_log_term > self.last_log_term) or (
                request.last_log_term == self.last_log_term and request.last_log_index >= self.last_log_index
            )
            if (self.voted_for in (None, request.candidate_id)) and up_to_date:
                self.voted_for = request.candidate_id
                self.current_term = request.term
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=True)

            return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)

    # ------------------------------------------------------------------
    # Commit and application helpers
    # ------------------------------------------------------------------
    def _update_commit_index(self) -> None:
        if self.state != "leader":
            return
        match_values = sorted(self.match_index.values())
        majority = len(self.peers) // 2 + 1
        if len(match_values) < majority:
            return
        new_commit = match_values[-majority]
        if new_commit > self.commit_index and new_commit > 0 and self.log[new_commit - 1].term == self.current_term:
            LOGGER.info("%s advancing commit index to %s", self.node_id, new_commit)
            self.commit_index = new_commit
            self._apply_committed_entries()

    def _apply_committed_entries(self) -> None:
        while self.last_applied < self.commit_index:
            entry = self.log[self.last_applied]
            self._apply_entry(entry)
            self.last_applied += 1
            if entry.index in self.pending_operations:
                self.pending_operations.remove(entry.index)

    def _apply_entry(self, entry: LogEntry) -> None:
        payload = json.loads(entry.command)
        op = payload.get("op")
        key = payload.get("key")
        value = payload.get("value")
        if op == "set" and key is not None:
            self.state_machine[key] = value
        elif op == "delete" and key is not None:
            self.state_machine.pop(key, None)
        LOGGER.info("%s applied entry %s -> %s", self.node_id, entry.index, self.state_machine)

    # ------------------------------------------------------------------
    # Client command used by the gRPC front door
    # ------------------------------------------------------------------
    def process_client_command(self, payload: str) -> raft_pb2.ClientCommandResponse:
        try:
            result = self.handle_client_payload(json.loads(payload))
            return raft_pb2.ClientCommandResponse(
                accepted=True,
                leader_id=self.node_id,
                leader_http_address=self.http_address,
                log_index=result["log_index"],
                commit_index=result["commit_index"],
                message="applied" if result["status"] == "ok" else "pending",
            )
        except NotLeaderError as exc:
            return raft_pb2.ClientCommandResponse(
                accepted=False,
                leader_id=exc.leader_id or self.leader_id or "",
                leader_http_address=exc.leader_http or self.leader_http_address or "",
                message="redirect",
            )

    # ------------------------------------------------------------------
    # Convenience helpers used by the HTTP shim
    # ------------------------------------------------------------------
    def forward_http(self, payload: Dict[str, str]) -> Dict[str, str]:
        if not self.leader_http_address:
            raise RuntimeError("leader unknown")
        import urllib.request

        req = urllib.request.Request(
            url=f"http://{self.leader_http_address}/client",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def shutdown(self) -> None:
        for channel in self._channel_cache.values():
            channel.close()
