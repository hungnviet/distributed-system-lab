#!/bin/bash

echo "🐳 Starting Docker services (Kafka, Zookeeper, etcd)..."
echo "========================================================"

# Start docker compose
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check status
echo ""
echo "Service status:"
docker-compose ps

echo ""
echo "✅ Docker services started!"
echo ""
echo "Services available at:"
echo "  - etcd: localhost:2379"
echo "  - Kafka: localhost:9092"
echo "  - Zookeeper: localhost:2181"
echo ""
echo "To check logs: docker-compose logs -f [service_name]"
echo "To stop: docker-compose down"
