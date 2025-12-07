#!/bin/bash

# Start script for gRPC Monitoring Server

echo "================================================"
echo "  Starting Monitoring Server"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Please run setup_monitoring.sh first:"
    echo "  ./setup_monitoring.sh"
    exit 1
fi

# Check if proto files have been generated
if [ ! -f "monitoring_pb2.py" ] || [ ! -f "monitoring_pb2_grpc.py" ]; then
    echo -e "${YELLOW}Warning: Generated proto files not found${NC}"
    echo "Generating them now..."
    source venv/bin/activate
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. monitoring.proto
    echo -e "${GREEN}✓${NC} Generated proto files"
    echo ""
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"
echo ""

# Start the monitoring server
echo -e "${BLUE}Starting monitoring server...${NC}"
echo ""
python monitoring_server.py
