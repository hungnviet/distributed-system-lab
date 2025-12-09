#!/bin/bash

echo "🖥️  Starting Lab 4 Monitoring Server..."
echo "========================================"

# Activate virtual environment
source venv/bin/activate

# Start server
cd server
python3 server.py 50052 localhost localhost:9092
