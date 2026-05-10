#!/bin/bash
# CPQM startup script — used by LaunchAgent and manual runs
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    /opt/homebrew/bin/python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python server.py
