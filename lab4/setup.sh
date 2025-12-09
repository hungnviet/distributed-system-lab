#!/bin/bash

echo "🔧 Lab 4 Setup Script"
echo "===================="

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Generate protobuf files
echo "Generating protobuf files..."
cd proto
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. monitoring.proto
cd ..

# Copy protobuf files to all directories
echo "Copying protobuf files..."
cp proto/monitoring_pb2.py proto/monitoring_pb2_grpc.py agent/
cp proto/monitoring_pb2.py proto/monitoring_pb2_grpc.py server/

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Start Docker services: docker-compose up -d"
echo "2. Wait for services to be ready (check with: docker-compose ps)"
echo "3. Start server: ./start_server.sh"
echo "4. Start agent: ./start_agent.sh"
echo "5. Start analysis: ./start_analysis.sh"
