import os
import time
import uuid
from typing import List

import grpc

import two_pc_pb2
import two_pc_pb2_grpc


def get_participants() -> List[str]:
    participants_env = os.getenv("PARTICIPANTS", "localhost:50051")
    return [participant.strip() for participant in participants_env.split(",") if participant.strip()]


def request_votes(participants: List[str]) -> bool:
    transaction_id = str(uuid.uuid4())
    votes = []

    for idx, participant in enumerate(participants, start=1):
        print(f"Phase voting of Node {idx} sends RPC RequestVote...")
        channel = grpc.insecure_channel(participant)
        stub = two_pc_pb2_grpc.TwoPCVotingStub(channel)
        try:
            response = stub.RequestVote(
                two_pc_pb2.VoteRequest(
                    transaction_id=transaction_id,
                    participant_id=f"participant-{idx}",
                    operation="prepare",
                )
            )
            decision = "COMMIT" if response.can_commit else "ABORT"
            print(
                f"Vote from {participant} ({response.participant_id}): {decision} - {response.message}"
            )
            votes.append(response.can_commit)
        except grpc.RpcError as exc:
            print(
                f"Vote request to {participant} failed with {exc.code().name}: {exc.details()}"
            )
            votes.append(False)

    overall_decision = all(votes) if votes else False
    print(
        f"Coordinator decision for transaction {transaction_id}: "
        f"{'COMMIT' if overall_decision else 'ABORT'}"
    )
    return overall_decision


def main():
    participants = get_participants()
    interval = int(os.getenv("VOTE_INTERVAL", "15"))

    print(f"Loaded participants: {participants}")
    print("Starting Two-Phase Commit coordinator loop")
    while True:
        request_votes(participants)
        time.sleep(interval)


if __name__ == "__main__":
    main()
