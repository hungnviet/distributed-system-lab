## 🚀 Quick Start (3 Commands)

```bash
./start_etcd.sh                    # 1. Start etcd
./start_server.sh                  # 2. Start server (new terminal)
./start_agent.sh                   # 3. Start agent (new terminal)
```

---

## 📋 Server Commands

```bash
Server> help                       # Show all commands
Server> health                     # Show all nodes (ALIVE/DEAD)
Server> list                       # Show connected gRPC clients
Server> stats                      # Show metrics statistics
Server> config node-1 '{"interval": 5, "metrics": ["cpu", "memory"]}'
Server> send agent-01 status       # Send command to agent
Server> quit                       # Shutdown
```

---

## ⚙️ Config Examples

```bash
# Fast monitoring - all metrics
Server> config $(hostname) {"interval": 2, "metrics": ["cpu", "memory", "disk", "network"]}

# Slow monitoring - minimal
Server> config $(hostname) {"interval": 30, "metrics": ["cpu"]}

# Network focused
Server> config $(hostname) {"interval": 5, "metrics": ["net in", "net out"]}

# Disk I/O monitoring
Server> config $(hostname) {"interval": 10, "metrics": ["disk read", "disk write"]}
```

config MiWiFi-R3-srv {"interval": 5, "metrics": ["cpu"]}
config MacBook-Pro-2.local {"interval": 3, "metrics": ["net in", "net out"]}

## 🐳 etcd Commands

```bash
# View all heartbeats
docker exec etcd-lab3 etcdctl get --prefix /monitor/heartbeat/

# View all configs
docker exec etcd-lab3 etcdctl get --prefix /monitor/config/

# View specific config
docker exec etcd-lab3 etcdctl get /monitor/config/$(hostname)

# Set config manually
docker exec etcd-lab3 etcdctl put /monitor/config/myhost '{"interval": 5, "metrics": ["cpu"]}'

# Delete key
docker exec etcd-lab3 etcdctl del /monitor/config/myhost

# etcd health check
docker exec etcd-lab3 etcdctl endpoint health
```

---

```bash
Server> config $(hostname) '{"interval": 2, "metrics": ["cpu"]}'
# Agent logs show: "Config change detected"
# Agent immediately changes behavior (no restart!)
```

```bash
Server> stats      # View aggregated metrics
Server> list       # View connected clients
# Check result.txt for logged data
```

## 🌐 Multi-Node Setup

### Server Node

```bash
NODE1_IP=$(hostname -I | awk '{print $1}')
./start_etcd.sh
./start_server.sh
echo "Connect agents to: $NODE1_IP:50052 and $NODE1_IP:2379"
```

### Agent Nodes

```bash
SERVER_IP="192.168.1.100" ## thay cái này thành địa chỉ IP của server
./start_agent.sh $SERVER_IP:50052 my-agent $SERVER_IP
```

IST-5G : 192.168.31.150
