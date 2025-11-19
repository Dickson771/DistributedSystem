#!/usr/bin/env python3

import os
import subprocess
import sys

def generate_proto_files():
    proto_dir = "protos"
    services = {
        "user": "user_service",
        "product": "product_service",
        "order": "order_service",
        "payment": "payment_service",
        "shipping": "shipping_service",
        "two_pc": "two_pc",
    }

    for service, output_dir in services.items():
        proto_file = os.path.join(proto_dir, f"{service}.proto")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate gRPC Python code
        cmd = [
            "python", "-m", "grpc_tools.protoc",
            f"--proto_path={proto_dir}",
            f"--python_out={output_dir}",
            f"--grpc_python_out={output_dir}",
            proto_file
        ]

        print(f"Generating code for {service}.proto...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error generating {service}.proto: {result.stderr}")
        else:
            print(f"Successfully generated {service}_pb2.py and {service}_pb2_grpc.py")

if __name__ == "__main__":
    generate_proto_files()
