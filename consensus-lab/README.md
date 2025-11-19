# Consensus Lab: 2PC + Raft Playground

This project adds a minimal **Two-Phase Commit (2PC)** and **Raft** implementation that runs five containerized nodes with gRPC.
The code is intentionally small so you can observe vote/decision messaging, leader election, heartbeats, log replication, and client request forwarding.

## Project Layout
- `protos/` – gRPC interface definitions for 2PC (`twopc.proto`) and Raft (`raft.proto`).
- `generated/` – Generated Python stubs (created by `generate_protos.py`).
- `node.py` – Combined server implementing both 2PC and Raft behaviors per node.
- `run_twopc.py` – Helper that triggers a 2PC transaction from the current node as coordinator.
- `docker-compose.yml` – Spins up five nodes with consistent addressing.
- `requirements.txt` – Python dependencies.

## Quickstart
1. **Generate gRPC code (only needed after editing protos):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python generate_protos.py
   ```

2. **Run the 5-node cluster locally via Docker:**
   ```bash
   docker compose up --build
   ```
   Each node logs heartbeats, leader elections, vote handling, and 2PC RPCs. Ports 50051-50055 are exposed on the host.

3. **Trigger a 2PC transaction (from any container):**
   ```bash
   # Example: run from node1 container
   docker exec -it consensus-node1 python run_twopc.py
   ```
   - Client log format (per requirements): `Phase <phase> of Node <id> sends RPC <name> to Phase <phase> of Node <id>`
   - Server log format: `Phase <phase> of Node <id> runs RPC <name> called by Phase <phase> of Node <id>`

4. **Send a Raft client request:**
   ```bash
   grpcurl -plaintext localhost:50051 raft.Raft/ClientRequest '{"operation":"set x=1"}'
   ```
   If the target is not leader, it forwards to the known leader and returns the latest log snapshot.

## Implementation Notes
- **2PC**
  - `ConsensusNode.run_twopc_transaction()` drives voting and decision phases; node3 is configured to abort (`ALLOW_COMMIT=false`) to show abort behavior.
  - RPC tracing follows the assignment’s client/server log format for both phases.
- **Raft**
  - Follower election timeouts are randomized between 1.5s–3s; heartbeat interval is 1s.
  - Entire logs are sent on every `AppendEntries` to satisfy the simplified replication requirement.
  - `ClientRequest` RPC forwards to the elected leader when needed; followers reply with forwarding info if no leader exists.

## Suggested Test Cases (Q5)
1. **Leader Election:** Start the cluster and observe one node becoming leader after randomized timeouts.
2. **Heartbeat Maintenance:** After election, verify followers reset timers through heartbeat `AppendEntries` logs.
3. **Client Forwarding:** Issue `ClientRequest` to a follower and confirm it forwards to the leader and returns the leader log.
4. **Log Replication:** Send multiple `ClientRequest` operations to the leader and confirm followers mirror the log entries on subsequent heartbeats.
5. **2PC Abort Path:** Trigger `run_twopc.py` from node1; with node3 set to abort, the coordinator should broadcast a global abort decision.

## External References
- Project brief on consensus algorithms and Raft/2PC basics (see assignment prompt).

