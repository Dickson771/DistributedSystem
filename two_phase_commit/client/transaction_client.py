import os

from two_phase_commit.coordinator.coordinator_service import Coordinator, parse_participants


def main() -> None:
    participants_raw = os.getenv("PARTICIPANTS", "")
    if not participants_raw:
        raise SystemExit("Client requires PARTICIPANTS env variable")
    endpoints = parse_participants(participants_raw)
    coordinator_id = os.getenv("COORDINATOR_ID", "client-coordinator")
    timeout = float(os.getenv("VOTE_TIMEOUT", "3"))
    amount = float(os.getenv("TX_AMOUNT", "25"))
    description = os.getenv("TX_DESCRIPTION", "demo purchase from client")
    operation = os.getenv("TX_OPERATION", "debit")

    print(
        f"[client] submitting transaction description='{description}' amount={amount} operation={operation}"
    )
    coordinator = Coordinator(coordinator_id, endpoints, timeout)
    coordinator.execute_transaction(description, amount, operation)
    print("[client] transaction request finished")


if __name__ == "__main__":
    main()
