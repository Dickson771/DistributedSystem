import pathlib
from grpc_tools import protoc

ROOT = pathlib.Path(__file__).parent
PROTO_DIR = ROOT / "protos"
GENERATED_DIR = ROOT / "generated"

GENERATED_DIR.mkdir(exist_ok=True)

protos = [
    (PROTO_DIR / "twopc.proto", GENERATED_DIR / "twopc_pb2.py"),
    (PROTO_DIR / "raft.proto", GENERATED_DIR / "raft_pb2.py"),
]

for proto, _ in protos:
    result = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={GENERATED_DIR}",
            f"--grpc_python_out={GENERATED_DIR}",
            str(proto),
        ]
    )
    if result != 0:
        raise SystemExit(f"Failed to generate code for {proto}")

print("Generated gRPC stubs in", GENERATED_DIR)
