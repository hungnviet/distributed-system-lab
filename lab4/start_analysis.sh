#!/bin/bash

echo "🔍 Starting Lab 4 Analysis Application..."
echo "=========================================="

# Default Kafka server
KAFKA_SERVERS=${1:-"localhost:9092"}

# Activate virtual environment
source venv/bin/activate

# Start analysis application
cd analysis
python3 analysis.py "$KAFKA_SERVERS"
