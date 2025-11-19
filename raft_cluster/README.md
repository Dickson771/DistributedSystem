# Raft Demo Cluster

This directory contains a lightweight Raft implementation written in Python. Each node exposes the `RequestVote` and `AppendEntries` RPCs described in `protos/raft.proto` and maintains follower/candidate/leader state using `asyncio` timers.

## Local development

1. (Optional) Regenerate the protobuf/gRPC stubs after editing the proto file:

   ```bash
   cd raft_cluster
   python generate_protos.py
   ```

2. Start a node locally with custom peers:

   ```bash
   python node.py --node-id 1 --peers localhost:50052
   ```

## Containerized cluster

The included `Dockerfile` builds a single Raft node image parameterized by environment variables:

- `RAFT_NODE_ID`: integer ID for the node.
- `RAFT_PEERS`: comma separated list of `host:port` entries for the other nodes.
- `RAFT_PORT` (optional): listening port (defaults to `50051`).

`docker-compose.yml` launches five nodes that discover each other using Docker's internal DNS entries (service names `node1`-`node5`). To run the demo cluster:

```bash
cd raft_cluster
docker compose up --build
```

Each container prints traces when elections, vote requests, and heartbeats occur so you can observe the state machine transitions.
