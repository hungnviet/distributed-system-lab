#!/bin/bash
# Test Lab 3 locally without Kubernetes

echo "==================================="
echo "Lab 3 Local Testing Script"
echo "==================================="

# Check if etcd is running
echo ""
echo "Checking if etcd is running..."
if ! docker ps | grep -q etcd-lab3; then
    echo "etcd is not running. Starting etcd..."
    ./start_etcd.sh
    sleep 3
else
    echo "✓ etcd is already running"
fi

# Initialize default configuration for current hostname
echo ""
echo "Initializing default configuration for $(hostname)..."
docker exec etcd-lab3 etcdctl put "/monitor/config/$(hostname)" '{"interval": 5, "metrics": ["cpu", "memory", "disk", "network"]}'

echo ""
echo "✓ Setup complete!"
echo ""
echo "Now you can:"
echo "  1. In Terminal 1: ./start_server.sh"
echo "  2. In Terminal 2: ./start_agent.sh"
echo "  3. In Terminal 3: ./start_agent.sh localhost:50052 agent-2"
echo ""
echo "To update configuration dynamically:"
echo "  docker exec etcd-lab3 etcdctl put /monitor/config/\$(hostname) '{\"interval\": 10, \"metrics\": [\"cpu\", \"memory\"]}'"
echo ""
echo "To view all configs:"
echo "  docker exec etcd-lab3 etcdctl get --prefix /monitor/config/"
echo ""
echo "To view all heartbeats:"
echo "  docker exec etcd-lab3 etcdctl get --prefix /monitor/heartbeat/"
echo ""
