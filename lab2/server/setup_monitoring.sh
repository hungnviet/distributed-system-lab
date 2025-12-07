#!/bin/bash

# Setup script for gRPC Monitoring System
# This script creates a virtual environment and installs dependencies

echo "================================================"
echo "  gRPC Monitoring System Setup"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}Step 1:${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} Found $PYTHON_VERSION"
echo ""

echo -e "${BLUE}Step 2:${NC} Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv
echo -e "${GREEN}✓${NC} Virtual environment created"
echo ""

echo -e "${BLUE}Step 3:${NC} Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"
echo ""

echo -e "${BLUE}Step 4:${NC} Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Pip upgraded"
echo ""

echo -e "${BLUE}Step 5:${NC} Installing dependencies..."
echo "  - grpcio (gRPC runtime)"
echo "  - grpcio-tools (Protocol buffer compiler)"
echo "  - protobuf (Protocol buffers)"
echo "  - psutil (System monitoring)"
pip install -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"
echo ""

echo -e "${BLUE}Step 6:${NC} Generating gRPC code from proto files..."
echo "  Generating from service.proto (Calculator service)..."
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. service.proto
echo -e "${GREEN}✓${NC} Generated service_pb2.py and service_pb2_grpc.py"

echo "  Generating from monitoring.proto (Monitoring service)..."
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. monitoring.proto
echo -e "${GREEN}✓${NC} Generated monitoring_pb2.py and monitoring_pb2_grpc.py"
echo ""

echo "================================================"
echo -e "${GREEN}✓ Setup completed successfully!${NC}"
echo "================================================"
echo ""
echo "Available services:"
echo "  1. Calculator Server (Lab Exercise 1)"
echo "     Start: ./start_server.sh"
echo ""
echo "  2. Monitoring Server (Lab Exercise 2)"
echo "     Start: ./start_monitoring_server.sh"
echo ""
