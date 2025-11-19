import os
import threading
from concurrent import futures

import grpc

from two_phase_commit.protos import two_pc_pb2, two_pc_pb2_grpc


class ParticipantState:
    def __init__(self, participant_id: str, initial_balance: float) -> None:
        self.participant_id = participant_id
        self.balance = initial_balance
        self.pending = {}
        self.committed = {}

    def _reserved_amount(self) -> float:
        reserved = 0.0
        for payload in self.pending.values():
            if payload.operation.lower() == "debit":
                reserved += payload.amount
        return reserved

    def can_debit(self, amount: float) -> bool:
        return (self.balance - self._reserved_amount()) >= amount

    def lock_transaction(self, payload: two_pc_pb2.TransactionPayload) -> tuple[bool, str]:
        if payload.transaction_id in self.pending:
            return True, "transaction already locked"
        op = payload.operation.lower()
        if op == "debit" and not self.can_debit(payload.amount):
            return False, "insufficient funds"
        self.pending[payload.transaction_id] = payload
        return True, f"reserved {payload.amount} for {op}"

    def apply_decision(self, txn_id: str, commit: bool) -> tuple[bool, str]:
        payload = self.pending.pop(txn_id, None)
        if payload is None:
            if commit:
                return False, "no pending transaction"
            return True, "no-op rollback"

        op = payload.operation.lower()
        if commit:
            if op == "debit":
                self.balance -= payload.amount
            else:
                self.balance += payload.amount
            self.committed[txn_id] = payload
            return True, f"committed {op} of {payload.amount}; balance={self.balance:.2f}"
        self.committed.pop(txn_id, None)
        return True, f"rolled back {op} of {payload.amount}; balance={self.balance:.2f}"


class VotingService(two_pc_pb2_grpc.VotingServiceServicer):
    def __init__(self, state: ParticipantState) -> None:
        self._state = state

    def Prepare(self, request: two_pc_pb2.VoteRequest, context: grpc.ServicerContext) -> two_pc_pb2.VoteResponse:  # noqa: N802
        payload = request.transaction
        print(
            f"[participant:{self._state.participant_id}] received Prepare for txn={payload.transaction_id} "
            f"op={payload.operation} amount={payload.amount}"
        )
        ok, reason = self._state.lock_transaction(payload)
        print(
            f"[participant:{self._state.participant_id}] vote={'COMMIT' if ok else 'ABORT'} for txn={payload.transaction_id}: {reason}"
        )
        return two_pc_pb2.VoteResponse(
            transaction_id=payload.transaction_id,
            participant_id=self._state.participant_id,
            vote=ok,
            reason=reason,
        )


class DecisionService(two_pc_pb2_grpc.DecisionServiceServicer):
    def __init__(self, state: ParticipantState) -> None:
        self._state = state

    def CommitOrAbort(self, request: two_pc_pb2.DecisionRequest, context: grpc.ServicerContext) -> two_pc_pb2.Ack:  # noqa: N802
        print(
            f"[participant:{self._state.participant_id}] received decision for txn={request.transaction_id}: "
            f"{'COMMIT' if request.commit else 'ABORT'}"
        )
        success, message = self._state.apply_decision(request.transaction_id, request.commit)
        print(f"[participant:{self._state.participant_id}] decision result txn={request.transaction_id}: {message}")
        return two_pc_pb2.Ack(
            transaction_id=request.transaction_id,
            participant_id=self._state.participant_id,
            applied=success,
            message=message,
        )


def _wait_forever(server: grpc.Server) -> None:
    server.wait_for_termination()


def serve() -> None:
    participant_id = os.getenv("PARTICIPANT_ID", "participant-a")
    initial_balance = float(os.getenv("INITIAL_BALANCE", "100"))
    voting_port = os.getenv("VOTING_PORT", "6000")
    decision_port = os.getenv("DECISION_PORT", "7000")

    state = ParticipantState(participant_id, initial_balance)

    voting_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    two_pc_pb2_grpc.add_VotingServiceServicer_to_server(VotingService(state), voting_server)
    voting_server.add_insecure_port(f"[::]:{voting_port}")

    decision_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    two_pc_pb2_grpc.add_DecisionServiceServicer_to_server(DecisionService(state), decision_server)
    decision_server.add_insecure_port(f"[::]:{decision_port}")

    print(
        f"[participant:{participant_id}] starting voting server on {voting_port} and decision server on {decision_port}"
    )

    voting_server.start()
    decision_server.start()

    decision_thread = threading.Thread(target=_wait_forever, args=(decision_server,), daemon=True)
    decision_thread.start()
    voting_server.wait_for_termination()


if __name__ == "__main__":
    serve()
