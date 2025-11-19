# Raft Log Replication Demo

This folder contains a lightweight Raft implementation that focuses on log
replication, leader heartbeats, and simple client forwarding.

## Layout

- `raft.proto` – RPC contract with log entries, heartbeat metadata, and
  client command plumbing.
- `node.py` – Core Raft state machine that replicates logs on heartbeats,
  applies committed prefixes, and produces ACK information.
- `service.py` – gRPC bindings plus helpers to construct a node from JSON
  configuration.
- `client_api.py` – Small HTTP façade that forwards client requests to the
  current leader when necessary.
- `run_node.py` – Utility wrapper that launches both the gRPC and HTTP
  servers for a node based on a config file.

## Running a node

1. Create a JSON file that lists the cluster peers. Example:

```json
{
  "node_id": "node-a",
  "grpc": "0.0.0.0:50051",
  "http": "127.0.0.1:8080",
  "leader": true,
  "peers": [
    {"node_id": "node-a", "grpc": "localhost:50051", "http": "127.0.0.1:8080"},
    {"node_id": "node-b", "grpc": "localhost:50052", "http": "127.0.0.1:8081"}
  ]
}
```

2. Launch the node:

```bash
python -m raft.run_node node-a.json
```

Client requests should be issued against the HTTP endpoint via `POST
/client` with JSON payloads like:

```json
{"op": "set", "key": "color", "value": "blue"}
```

Followers automatically forward to the leader. RPC tracing is emitted to the
console for every request to make debugging easier.
