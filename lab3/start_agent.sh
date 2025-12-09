#!/bin/bash
# Start Lab 3 Monitoring Agent

SERVER_ADDRESS=${1:-localhost:50052}
CLIENT_ID=${2:-agent-$(hostname)-$$}
ETCD_HOST=${3:-localhost}

echo "Starting Lab 3 Monitoring Agent..."
echo "  Server: $SERVER_ADDRESS"
echo "  Client ID: $CLIENT_ID"
echo "  etcd: $ETCD_HOST:2379"
echo ""

cd agent
python agent.py $SERVER_ADDRESS $CLIENT_ID $ETCD_HOST
