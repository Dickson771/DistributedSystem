import os
from concurrent import futures

import grpc

import two_pc_pb2
import two_pc_pb2_grpc


class TwoPCVotingService(two_pc_pb2_grpc.TwoPCVotingServicer):
    def __init__(self, participant_id: str, vote_decision: str):
        self.participant_id = participant_id
        self.vote_decision = vote_decision.lower()

    def RequestVote(self, request, context):
        decision = self.vote_decision != "abort"
        message = (
            f"Participant {self.participant_id} voting commit"
            if decision
            else f"Participant {self.participant_id} voting abort"
        )
        print(
            f"Received vote request for transaction {request.transaction_id} "
            f"on participant {self.participant_id} with operation '{request.operation}'"
        )
        return two_pc_pb2.VoteResponse(
            can_commit=decision,
            participant_id=self.participant_id,
            message=message,
        )


def serve():
    port = os.getenv("VOTING_PORT", "50051")
    participant_id = os.getenv("PARTICIPANT_ID", f"participant-{port}")
    vote_decision = os.getenv("VOTE_DECISION", "commit")

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    two_pc_pb2_grpc.add_TwoPCVotingServicer_to_server(
        TwoPCVotingService(participant_id, vote_decision), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(
        f"TwoPC Voting server for {participant_id} running on port {port} "
        f"with default decision '{vote_decision}'"
    )
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
