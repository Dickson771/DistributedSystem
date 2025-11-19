import logging
import os
import random
import threading
import time
from concurrent import futures
from typing import Dict, List, Optional

import grpc

from generated import raft_pb2, raft_pb2_grpc, twopc_pb2, twopc_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


class TwoPhaseCommitService(twopc_pb2_grpc.TwoPhaseCommitServicer):
    def __init__(self, node_id: str, allow_commit: bool = True):
        self.node_id = node_id
        self.allow_commit = allow_commit
        self.decisions: Dict[str, bool] = {}

    def VoteRequest(self, request, context):
        logging.info(
            "Phase Voting of Node %s runs RPC VoteRequest called by Phase Voting of Node %s",
            self.node_id,
            request.coordinator_id,
        )
        commit_ready = self.allow_commit
        explanation = (
            "Prepared to commit"
            if commit_ready
            else "Participant is configured to abort"
        )
        return twopc_pb2.VoteResponseMessage(
            commit_ready=commit_ready,
            participant_id=self.node_id,
            explanation=explanation,
        )

    def Decision(self, request, context):
        logging.info(
            "Phase Decision of Node %s runs RPC Decision called by Phase Decision of Node %s",
            self.node_id,
            request.coordinator_id,
        )
        self.decisions[request.transaction_id] = request.commit
        return twopc_pb2.DecisionAck(
            participant_id=self.node_id,
            committed=request.commit,
        )


class RaftService(raft_pb2_grpc.RaftServicer):
    def __init__(self, node):
        self.node = node

    def RequestVote(self, request, context):
        self.node.log_server_message("RequestVote", request.candidate_id)
        with self.node.lock:
            if request.term < self.node.current_term:
                return raft_pb2.RequestVoteResponse(
                    term=self.node.current_term, vote_granted=False
                )
            if request.term > self.node.current_term:
                self.node.become_follower(request.term)
            grant = False
            if (
                (self.node.voted_for is None or self.node.voted_for == request.candidate_id)
            ):
                self.node.voted_for = request.candidate_id
                grant = True
                self.node.reset_election_timer()
            return raft_pb2.RequestVoteResponse(
                term=self.node.current_term,
                vote_granted=grant,
            )

    def AppendEntries(self, request, context):
        self.node.log_server_message("AppendEntries", request.leader_id)
        with self.node.lock:
            if request.term < self.node.current_term:
                return raft_pb2.AppendEntriesResponse(
                    term=self.node.current_term, success=False
                )
            if request.term > self.node.current_term:
                self.node.become_follower(request.term)
            self.node.leader_id = request.leader_id
            self.node.reset_election_timer()
            # Replace log with leader's for simplicity (requirement: send entire log)
            self.node.log = list(request.entries)
            self.node.commit_index = request.leader_commit
            return raft_pb2.AppendEntriesResponse(
                term=self.node.current_term, success=True
            )

    def ClientRequest(self, request, context):
        caller = "client"
        if self.node.state != "leader":
            # forward to leader if known
            leader = self.node.leader_id
            if leader is None:
                return raft_pb2.ClientResponse(
                    forwarded=False,
                    leader_id="unknown",
                    log=[],
                    status="No leader elected yet",
                )
            self.node.log_client_message("ClientRequest", caller, leader)
            stub = self.node.stubs.get(leader)
            if stub is None:
                return raft_pb2.ClientResponse(
                    forwarded=False,
                    leader_id=leader,
                    log=[],
                    status="Leader not reachable",
                )
            response = stub.ClientRequest(request)
            return response

        self.node.log_client_message("ClientRequest", caller, self.node.node_id)
        with self.node.lock:
            next_index = len(self.node.log) + 1
            self.node.log.append(
                raft_pb2.LogEntry(index=next_index, term=self.node.current_term, command=request.operation)
            )
        return raft_pb2.ClientResponse(
            forwarded=False,
            leader_id=self.node.node_id,
            log=list(self.node.log),
            status="Operation appended on leader",
        )


class ConsensusNode:
    def __init__(self, node_id: str, address: str, peers: Dict[str, str], allow_commit: bool = True):
        self.node_id = node_id
        self.address = address
        self.peers = peers
        self.allow_commit = allow_commit

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        twopc_pb2_grpc.add_TwoPhaseCommitServicer_to_server(
            TwoPhaseCommitService(node_id, allow_commit=allow_commit), self.server
        )
        raft_pb2_grpc.add_RaftServicer_to_server(RaftService(self), self.server)
        self.server.add_insecure_port(self.address)

        self.stubs: Dict[str, raft_pb2_grpc.RaftStub] = {}
        self.twopc_stubs: Dict[str, twopc_pb2_grpc.TwoPhaseCommitStub] = {}
        self._build_stubs()

        # Raft state
        self.lock = threading.RLock()
        self.state = "follower"
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[raft_pb2.LogEntry] = []
        self.commit_index = 0
        self.leader_id: Optional[str] = None
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_timeout()
        self.heartbeat_interval = 1.0
        self.running = True

    def _build_stubs(self):
        for peer_id, peer_address in self.peers.items():
            channel = grpc.insecure_channel(peer_address)
            self.stubs[peer_id] = raft_pb2_grpc.RaftStub(channel)
            self.twopc_stubs[peer_id] = twopc_pb2_grpc.TwoPhaseCommitStub(channel)

    def start(self):
        self.server.start()
        logging.info("Node %s started at %s", self.node_id, self.address)
        threading.Thread(target=self._raft_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.server.stop(0)

    # --- Two Phase Commit coordinator utilities ---
    def run_twopc_transaction(self, payload: str) -> bool:
        transaction_id = f"txn-{int(time.time() * 1000)}"
        votes: List[twopc_pb2.VoteResponseMessage] = []
        # Voting phase
        for participant_id, stub in self.twopc_stubs.items():
            self.log_phase_message("Voting", self.node_id, participant_id, "VoteRequest")
            response = stub.VoteRequest(
                twopc_pb2.VoteRequestMessage(
                    transaction_id=transaction_id,
                    payload=payload,
                    coordinator_id=self.node_id,
                )
            )
            votes.append(response)
        decision = all(v.commit_ready for v in votes)
        # Decision phase
        for participant_id, stub in self.twopc_stubs.items():
            self.log_phase_message("Decision", self.node_id, participant_id, "Decision")
            stub.Decision(
                twopc_pb2.DecisionRequest(
                    transaction_id=transaction_id,
                    coordinator_id=self.node_id,
                    commit=decision,
                )
            )
        return decision

    @staticmethod
    def log_phase_message(phase: str, from_id: str, to_id: str, rpc_name: str):
        logging.info(
            "Phase %s of Node %s sends RPC %s to Phase %s of Node %s",
            phase,
            from_id,
            rpc_name,
            phase,
            to_id,
        )

    def log_client_message(self, rpc_name: str, from_id: str, to_id: str):
        logging.info(
            "Node %s sends RPC %s to Node %s",
            from_id,
            rpc_name,
            to_id,
        )

    def log_server_message(self, rpc_name: str, caller_id: str):
        logging.info(
            "Node %s runs RPC %s called by Node %s",
            self.node_id,
            rpc_name,
            caller_id,
        )

    # --- Raft internals ---
    def _random_timeout(self) -> float:
        return random.uniform(1.5, 3.0)

    def reset_election_timer(self):
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_timeout()

    def become_follower(self, term: int):
        self.state = "follower"
        self.current_term = term
        self.voted_for = None
        self.leader_id = None
        self.reset_election_timer()

    def become_leader(self):
        self.state = "leader"
        self.leader_id = self.node_id
        logging.info("Node %s became leader for term %s", self.node_id, self.current_term)

    def _raft_loop(self):
        while self.running:
            time.sleep(0.1)
            if self.state == "leader":
                self._send_heartbeats()
            else:
                if time.time() - self.last_heartbeat > self.election_timeout:
                    self._start_election()

    def _start_election(self):
        with self.lock:
            self.state = "candidate"
            self.current_term += 1
            self.voted_for = self.node_id
            self.reset_election_timer()
            term = self.current_term
        votes = 1  # self vote
        for peer_id, stub in self.stubs.items():
            self.log_client_message("RequestVote", self.node_id, peer_id)
            try:
                response = stub.RequestVote(
                    raft_pb2.RequestVoteRequest(
                        term=term,
                        candidate_id=self.node_id,
                        last_log_index=len(self.log),
                        last_log_term=self.log[-1].term if self.log else 0,
                    )
                )
                if response.vote_granted:
                    votes += 1
            except grpc.RpcError as exc:
                logging.warning("RequestVote to %s failed: %s", peer_id, exc)
        if votes > (len(self.peers) + 1) // 2:
            with self.lock:
                self.become_leader()
        else:
            with self.lock:
                self.state = "follower"

    def _send_heartbeats(self):
        with self.lock:
            term = self.current_term
            entries = list(self.log)
            commit_index = self.commit_index
        for peer_id, stub in self.stubs.items():
            self.log_client_message("AppendEntries", self.node_id, peer_id)
            try:
                response = stub.AppendEntries(
                    raft_pb2.AppendEntriesRequest(
                        term=term,
                        leader_id=self.node_id,
                        entries=entries,
                        leader_commit=commit_index,
                    )
                )
                if response.success:
                    # increment commit index when majority acks
                    pass
            except grpc.RpcError as exc:
                logging.warning("AppendEntries to %s failed: %s", peer_id, exc)
        time.sleep(self.heartbeat_interval)



def load_peers_from_env(node_id: str) -> Dict[str, str]:
    peers_env = os.environ.get("PEERS", "")
    peers: Dict[str, str] = {}
    for entry in peers_env.split(","):
        if not entry:
            continue
        name, address = entry.split("=")
        if name != node_id:
            peers[name] = address
    return peers


def main():
    node_id = os.environ.get("NODE_ID", "node1")
    address = os.environ.get("ADDRESS", "0.0.0.0:50051")
    peers = load_peers_from_env(node_id)
    allow_commit = os.environ.get("ALLOW_COMMIT", "true").lower() == "true"

    node = ConsensusNode(node_id=node_id, address=address, peers=peers, allow_commit=allow_commit)
    node.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()


if __name__ == "__main__":
    main()
