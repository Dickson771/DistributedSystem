#!/bin/bash
set -euo pipefail

python -m two_phase_commit.client.transaction_client
