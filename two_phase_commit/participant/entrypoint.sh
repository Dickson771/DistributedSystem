#!/bin/bash
set -euo pipefail

python -m two_phase_commit.participant.participant_service
