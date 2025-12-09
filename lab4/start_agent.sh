#!/bin/bash

echo "🤖 Starting Lab 4 Monitoring Agent..."
echo "======================================"

# Default values
SERVER_ADDRESS=${1:-"localhost:50052"}
CLIENT_ID=${2:-""}
ETCD_HOST=${3:-"localhost"}

# Activate virtual environment
source venv/bin/activate

# Start agent
cd agent
python3 agent.py "$SERVER_ADDRESS" "$CLIENT_ID" "$ETCD_HOST"
