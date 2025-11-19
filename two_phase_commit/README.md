# Two-Phase Commit Demo

This folder contains a lightweight reference implementation of a two-phase commit (2PC) workflow built with Python and gRPC. It contains:

- `protos/` – shared protobuf definitions (`two_pc.proto`) plus the generated gRPC stubs.
- `participant/` – code for a participant that exposes independent voting and decision services.
- `coordinator/` – the coordinator logic that collects votes, determines the global decision, and sends `CommitOrAbort` RPCs to every participant with timeout/abort handling.
- `client/` – a thin wrapper that invokes the coordinator logic and prints out a trace of the request lifecycle.
- `docker-compose.yml` – spins up two participant containers and a client container on a shared bridge network so the gRPC calls flow across nodes.

## Running with Docker Compose

```bash
cd two_phase_commit
# Build containers and run a demo transaction
VOTE_TIMEOUT=5 docker compose up --build
```

You will see log lines similar to the following that confirm both the client and the participants trace the workflow:

```
participant_a  | [participant:participant-a] received Prepare for txn=...
participant_a  | [participant:participant-a] vote=COMMIT ...
participant_b  | [participant:participant-b] vote=ABORT ...
client         | [client] submitting transaction ...
client         | [coordinator:cli-coordinator] aggregate decision=ABORT
client         | [client] transaction request finished
```

The exposed ports (6100/6200 for `participant_a` and 6300/6400 for `participant_b`) allow you to drive manual tests from the host if desired. Adjust `TX_AMOUNT`/`TX_OPERATION`/`INITIAL_BALANCE` environment variables in `docker-compose.yml` to verify both commit and abort paths.

## Local Development

1. Install the dependencies (Python 3.11+ recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r participant/requirements.txt
   ```

2. Regenerate protobuf stubs after editing `protos/two_pc.proto`:

   ```bash
   python -m grpc_tools.protoc -I protos --python_out=protos --grpc_python_out=protos protos/two_pc.proto
   ```

3. Run a participant locally:

   ```bash
   PARTICIPANT_ID=participant-a VOTING_PORT=6100 DECISION_PORT=6200 \
   python -m two_phase_commit.participant.participant_service
   ```

4. Run the demo client (which exercises the coordinator logic):

   ```bash
   PARTICIPANTS=localhost:6100:6200 TX_AMOUNT=40 TX_OPERATION=debit \
   python -m two_phase_commit.client.transaction_client
   ```

   The coordinator prints each RPC call it makes while the participants log their local decisions, making it easy to follow the end-to-end transaction.
