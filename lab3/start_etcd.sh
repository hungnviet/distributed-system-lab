#!/bin/bash
# Start etcd using Docker for local testing

echo "Starting etcd container..."

# Check if etcd container already exists
if [ "$(docker ps -aq -f name=etcd-lab3)" ]; then
    echo "Removing existing etcd container..."
    docker rm -f etcd-lab3
fi

# Start etcd
docker run -d --name etcd-lab3 \
  -p 2379:2379 \
  -p 2380:2380 \
  quay.io/coreos/etcd:v3.5.0 \
  /usr/local/bin/etcd \
  --name etcd0 \
  --advertise-client-urls http://0.0.0.0:2379 \
  --listen-client-urls http://0.0.0.0:2379 \
  --initial-advertise-peer-urls http://0.0.0.0:2380 \
  --listen-peer-urls http://0.0.0.0:2380 \
  --initial-cluster etcd0=http://0.0.0.0:2380

echo ""
echo "✓ etcd started successfully!"
echo ""
echo "etcd is now running at: localhost:2379"
echo ""
echo "To check status: docker logs etcd-lab3"
echo "To stop etcd:    docker stop etcd-lab3"
echo "To remove etcd:  docker rm etcd-lab3"
echo ""

# Wait a bit for etcd to start
sleep 2

# Test connection
echo "Testing etcd connection..."
docker exec etcd-lab3 etcdctl endpoint health

echo ""
echo "You can now initialize agent configurations:"
echo "  docker exec etcd-lab3 etcdctl put /monitor/config/\$(hostname) '{\"interval\": 5, \"metrics\": [\"cpu\", \"memory\", \"disk\"]}'"
echo ""
