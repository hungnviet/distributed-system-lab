#!/bin/bash
# Lab 3 Setup Script

echo "==================================="
echo "Lab 3 Monitoring Tool Setup"
echo "==================================="

# Install Python dependencies
echo ""
echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt

# Generate gRPC code
echo ""
echo "[2/3] Generating gRPC code from proto..."
python -m grpc_tools.protoc -I./proto --python_out=./agent --grpc_python_out=./agent proto/monitoring.proto
python -m grpc_tools.protoc -I./proto --python_out=./server --grpc_python_out=./server proto/monitoring.proto

# Make scripts executable
echo ""
echo "[3/3] Making scripts executable..."
chmod +x agent/agent.py
chmod +x server/server.py
chmod +x start_etcd.sh
chmod +x start_server.sh
chmod +x start_agent.sh

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start etcd:   ./start_etcd.sh"
echo "  2. Start server: ./start_server.sh"
echo "  3. Start agent:  ./start_agent.sh"
echo ""
