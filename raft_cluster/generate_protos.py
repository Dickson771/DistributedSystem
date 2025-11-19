#!/usr/bin/env python3
"""Generate gRPC stubs for the Raft service."""

from __future__ import annotations

import pathlib
import subprocess
import sys


def main() -> None:
    root = pathlib.Path(__file__).parent.resolve()
    proto_dir = root / "protos"
    proto_file = proto_dir / "raft.proto"

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={proto_dir}",
        f"--python_out={root}",
        f"--grpc_python_out={root}",
        str(proto_file),
    ]

    print("Generating gRPC artifacts from", proto_file)
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
