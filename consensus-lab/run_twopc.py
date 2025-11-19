import os
import time

from node import ConsensusNode, load_peers_from_env


def main():
    node_id = os.environ.get("NODE_ID", "coordinator")
    address = os.environ.get("ADDRESS", "0.0.0.0:60000")
    peers = load_peers_from_env(node_id)

    # Build coordinator instance without starting server
    coordinator = ConsensusNode(node_id=node_id, address=address, peers=peers)
    payload = os.environ.get("PAYLOAD", "demo-action")
    decision = coordinator.run_twopc_transaction(payload)
    status = "COMMIT" if decision else "ABORT"
    print(f"Transaction result: {status} for payload '{payload}' at {time.ctime()}")


if __name__ == "__main__":
    main()
