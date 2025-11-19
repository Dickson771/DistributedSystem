import argparse
import os
import uuid
from dataclasses import dataclass
from typing import List

import grpc

from two_phase_commit.protos import two_pc_pb2, two_pc_pb2_grpc


@dataclass
class ParticipantEndpoint:
    name: str
    voting_target: str
    decision_target: str


def parse_participants(raw: str) -> List[ParticipantEndpoint]:
    endpoints: List[ParticipantEndpoint] = []
    for spec in raw.split(","):
        spec = spec.strip()
        if not spec:
            continue
        parts = spec.split(":")
        if len(parts) < 3:
            raise ValueError(
                "Each participant definition must look like 'service-name:voting-port:decision-port'"
            )
        name = parts[0]
        voting_port = parts[1]
        decision_port = parts[2]
        host = name
        endpoints.append(
            ParticipantEndpoint(
                name=name,
                voting_target=f"{host}:{voting_port}",
                decision_target=f"{host}:{decision_port}",
            )
        )
    return endpoints


class Coordinator:
    def __init__(self, coordinator_id: str, participants: List[ParticipantEndpoint], vote_timeout: float) -> None:
        self.coordinator_id = coordinator_id
        self.participants = participants
        self.vote_timeout = vote_timeout

    def _send_vote_request(
        self, endpoint: ParticipantEndpoint, payload: two_pc_pb2.TransactionPayload
    ) -> two_pc_pb2.VoteResponse | None:
        target = endpoint.voting_target
        request = two_pc_pb2.VoteRequest(participant_id=endpoint.name, transaction=payload)
        print(f"[coordinator:{self.coordinator_id}] sending Prepare to {endpoint.name} at {target}")
        with grpc.insecure_channel(target) as channel:
            stub = two_pc_pb2_grpc.VotingServiceStub(channel)
            try:
                response = stub.Prepare(request, timeout=self.vote_timeout)
                print(
                    f"[coordinator:{self.coordinator_id}] {endpoint.name} voted "
                    f"{'COMMIT' if response.vote else 'ABORT'} ({response.reason})"
                )
                return response
            except grpc.RpcError as exc:  # pragma: no cover - network errors are runtime events
                print(
                    f"[coordinator:{self.coordinator_id}] vote request to {endpoint.name} failed: {exc.code().name}"
                )
                return None

    def _broadcast_decision(self, commit: bool, payload: two_pc_pb2.TransactionPayload) -> None:
        for endpoint in self.participants:
            target = endpoint.decision_target
            request = two_pc_pb2.DecisionRequest(
                transaction_id=payload.transaction_id,
                commit=commit,
                coordinator_id=self.coordinator_id,
            )
            print(
                f"[coordinator:{self.coordinator_id}] sending decision {'COMMIT' if commit else 'ABORT'} to {endpoint.name}"
            )
            with grpc.insecure_channel(target) as channel:
                stub = two_pc_pb2_grpc.DecisionServiceStub(channel)
                try:
                    ack = stub.CommitOrAbort(request, timeout=self.vote_timeout)
                    print(
                        f"[coordinator:{self.coordinator_id}] {endpoint.name} applied decision: {ack.message}"
                    )
                except grpc.RpcError as exc:  # pragma: no cover
                    print(
                        f"[coordinator:{self.coordinator_id}] failed to deliver decision to {endpoint.name}: "
                        f"{exc.code().name}"
                    )

    def execute_transaction(self, description: str, amount: float, operation: str) -> None:
        payload = two_pc_pb2.TransactionPayload(
            transaction_id=str(uuid.uuid4()),
            description=description,
            amount=amount,
            operation=operation,
        )
        print(
            f"[coordinator:{self.coordinator_id}] starting transaction txn={payload.transaction_id} "
            f"operation={operation} amount={amount}"
        )
        votes = []
        for endpoint in self.participants:
            response = self._send_vote_request(endpoint, payload)
            if response is not None:
                votes.append(response)

        commit = len(votes) == len(self.participants) and all(v.vote for v in votes)
        print(
            f"[coordinator:{self.coordinator_id}] aggregate decision={'COMMIT' if commit else 'ABORT'}"
        )
        self._broadcast_decision(commit, payload)
        print(f"[coordinator:{self.coordinator_id}] transaction {payload.transaction_id} finished")


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-phase commit coordinator demo")
    parser.add_argument("description", nargs="?", default="demo purchase")
    parser.add_argument("--amount", type=float, default=10.0)
    parser.add_argument("--operation", choices=["credit", "debit"], default="debit")
    parser.add_argument("--participants", default=os.getenv("PARTICIPANTS", ""))
    parser.add_argument("--coordinator-id", default=os.getenv("COORDINATOR_ID", "coordinator"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("VOTE_TIMEOUT", "3")))
    args = parser.parse_args()

    participants_raw = args.participants or os.getenv("PARTICIPANTS", "")
    if not participants_raw:
        raise SystemExit("No participants configured. Set --participants or PARTICIPANTS env var.")

    endpoints = parse_participants(participants_raw)
    coordinator = Coordinator(args.coordinator_id, endpoints, args.timeout)
    coordinator.execute_transaction(args.description, args.amount, args.operation)


if __name__ == "__main__":
    main()
