# Lab 4: Distributed Monitoring System with Plugin Architecture

A comprehensive monitoring system integrating **gRPC**, **etcd**, **Kafka**, and a **plugin architecture** for extensible monitoring agents.

## 🏗️ Architecture Overview

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────┐
│  Monitor Agent  │──gRPC──>│ gRPC Server  │──────>│    Kafka    │
│  (with plugins) │<──cmd───│  (Broker)    │<──────│ (Streaming) │
└─────────────────┘         └──────────────┘         └─────────────┘
        │                           │                        │
        │ heartbeat                 │ health                 │
        │ & config                  │ check                  │ consume
        v                           v                        v
┌─────────────────┐         ┌──────────────┐         ┌─────────────┐
│      etcd       │         │     etcd     │         │  Analysis   │
│ (Config Store)  │         │  (Registry)  │         │     App     │
└─────────────────┘         └──────────────┘         └─────────────┘
```

### Components:

1. **Monitor Agent** (with Plugin Architecture)
   - Collects system metrics (CPU, memory, disk, network)
   - Dynamically loads plugins from etcd configuration
   - Sends heartbeat to etcd
   - Communicates with gRPC server

2. **gRPC Server** (Broker)
   - Receives monitoring data from agents
   - Forwards data to Kafka
   - Consumes commands from Kafka
   - Forwards commands to agents
   - Monitors node health via etcd

3. **Kafka** (Message Broker)
   - Streams monitoring data
   - Queues commands for agents

4. **Analysis Application**
   - Consumes data from Kafka
   - Prints metrics to stdout
   - Sends commands to agents via Kafka

5. **etcd** (Configuration & Service Registry)
   - Stores agent configurations
   - Tracks node health via heartbeats

---

## 🔌 Plugin Architecture

### Available Plugins:

1. **DuplicateFilterPlugin** (`plugins.duplicate_filter.DuplicateFilterPlugin`)
   - Filters duplicate metrics to reduce network bandwidth
   - Only sends data when values change

2. **ThresholdAlertPlugin** (`plugins.threshold_alert.ThresholdAlertPlugin`)
   - Monitors metrics against thresholds
   - Logs alerts when thresholds exceeded
   - Default thresholds: CPU 80%, Memory 85%, Disk 90%

3. **LoggerPlugin** (`plugins.logger.LoggerPlugin`)
   - Logs all metrics for debugging

### Creating Custom Plugins:

Create a new file in `plugins/` directory:

```python
from plugins.base import BasePlugin

class MyCustomPlugin(BasePlugin):
    def initialize(self, config=None):
        # Initialize plugin
        pass

    def run(self, data):
        # Process data
        return data

    def finalize(self):
        # Cleanup
        pass
```

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
./setup.sh
```

This will:
- Create Python virtual environment
- Install dependencies
- Generate protobuf files

### 2. Start Docker Services

```bash
./start_docker.sh
```

Services:
- **etcd**: localhost:2379
- **Kafka**: localhost:9092
- **Zookeeper**: localhost:2181

### 3. Start Components (in separate terminals)

**Terminal 1 - gRPC Server:**
```bash
./start_server.sh
```

**Terminal 2 - Monitor Agent:**
```bash
./start_agent.sh
```

**Terminal 3 - Analysis Application:**
```bash
./start_analysis.sh
```

---

## ⚙️ Configuration

### Agent Configuration Format

Store in etcd at `/monitor/config/<hostname>`:

```json
{
  "interval": 5,
  "metrics": ["cpu", "memory", "disk read", "disk write", "net in", "net out"],
  "plugins": [
    "plugins.duplicate_filter.DuplicateFilterPlugin",
    "plugins.threshold_alert.ThresholdAlertPlugin"
  ],
  "plugin_configs": {
    "ThresholdAlertPlugin": {
      "cpu": 80,
      "memory": 90,
      "disk": 95
    }
  }
}
```

### Update Configuration via Server

```bash
Server> config $(hostname) '{"interval": 2, "metrics": ["cpu", "memory"], "plugins": ["plugins.duplicate_filter.DuplicateFilterPlugin"]}'
```

The agent will automatically reload plugins when configuration changes!

---

## 📋 Available Commands

### gRPC Server Commands

```bash
Server> help                       # Show all commands
Server> list                       # List connected agents
Server> health                     # Show node health status
Server> stats                      # Show monitoring statistics
Server> config <host> <json>       # Update agent configuration
Server> send <client_id> <cmd>     # Send command to agent
Server> quit                       # Shutdown server
```

### Analysis Application Commands

```bash
Analysis> help                     # Show help
Analysis> stats                    # Show statistics
Analysis> send <target> <command>  # Send command to agent(s)
                                   # target: client_id or 'all'
Analysis> quit                     # Exit application
```

### Examples:

```bash
# From Analysis App - send status command to all agents
Analysis> send all status

# From Analysis App - send to specific agent
Analysis> send my-agent status

# From Server - update config with plugins
Server> config $(hostname) '{"interval": 3, "plugins": ["plugins.duplicate_filter.DuplicateFilterPlugin", "plugins.threshold_alert.ThresholdAlertPlugin"]}'
```

---

## 🐳 Docker Management

### Check Service Status
```bash
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f kafka
docker-compose logs -f etcd
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

---

## 🔍 Kafka Topics

### View Topics
```bash
docker exec kafka-lab4 kafka-topics --list --bootstrap-server localhost:9092
```

### Monitor Data Topic
```bash
docker exec kafka-lab4 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic monitoring-data \
  --from-beginning
```

### Monitor Command Topic
```bash
docker exec kafka-lab4 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic monitoring-commands \
  --from-beginning
```

### Send Test Command to Kafka
```bash
docker exec -it kafka-lab4 kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic monitoring-commands

# Then type:
{"command_id": "test1", "target": "all", "command_type": "status", "timestamp": 1234567890}
```

---

## 🗂️ etcd Operations

### View All Configurations
```bash
docker exec etcd-lab4 etcdctl get --prefix /monitor/config/
```

### View Heartbeats
```bash
docker exec etcd-lab4 etcdctl get --prefix /monitor/heartbeat/
```

### Set Configuration Manually
```bash
docker exec etcd-lab4 etcdctl put /monitor/config/myhost \
  '{"interval": 5, "metrics": ["cpu"], "plugins": ["plugins.logger.LoggerPlugin"]}'
```

### Delete Configuration
```bash
docker exec etcd-lab4 etcdctl del /monitor/config/myhost
```

---

## 🌐 Multi-Node Setup

### Server Node
```bash
# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

# Start services
./start_docker.sh
./start_server.sh
./start_analysis.sh

echo "Agents should connect to: $SERVER_IP:50052"
echo "etcd available at: $SERVER_IP:2379"
```

### Agent Nodes
```bash
SERVER_IP="192.168.1.100"  # Replace with actual server IP

# Start agent with remote server and etcd
./start_agent.sh $SERVER_IP:50052 my-agent $SERVER_IP
```

---

## 📊 Data Flow

1. **Agent → Server**: Metrics via gRPC bidirectional stream
2. **Server → Kafka**: Monitoring data published to `monitoring-data` topic
3. **Kafka → Analysis**: Analysis app consumes from `monitoring-data` topic
4. **Analysis → Kafka**: Commands published to `monitoring-commands` topic
5. **Kafka → Server**: Server consumes commands from `monitoring-commands` topic
6. **Server → Agent**: Commands forwarded via gRPC stream

---

## 🔧 Plugin Examples

### Example 1: Enable Duplicate Filter Only
```bash
Server> config $(hostname) '{
  "interval": 5,
  "metrics": ["cpu", "memory"],
  "plugins": ["plugins.duplicate_filter.DuplicateFilterPlugin"]
}'
```

### Example 2: Enable All Plugins with Custom Thresholds
```bash
Server> config $(hostname) '{
  "interval": 3,
  "metrics": ["cpu", "memory", "disk"],
  "plugins": [
    "plugins.duplicate_filter.DuplicateFilterPlugin",
    "plugins.threshold_alert.ThresholdAlertPlugin",
    "plugins.logger.LoggerPlugin"
  ],
  "plugin_configs": {
    "ThresholdAlertPlugin": {
      "cpu": 70,
      "memory": 80,
      "disk": 90
    },
    "LoggerPlugin": {
      "enabled": true
    }
  }
}'
```

### Example 3: Disable All Plugins
```bash
Server> config $(hostname) '{
  "interval": 5,
  "metrics": ["cpu", "memory"],
  "plugins": []
}'
```

---

## 🐛 Troubleshooting

### Check if services are running
```bash
docker-compose ps
```

### Kafka connection issues
```bash
# Check Kafka health
docker exec kafka-lab4 kafka-broker-api-versions --bootstrap-server localhost:9092

# Restart Kafka
docker-compose restart kafka
```

### etcd connection issues
```bash
# Check etcd health
docker exec etcd-lab4 etcdctl endpoint health

# Restart etcd
docker-compose restart etcd
```

### Agent not receiving config updates
```bash
# Verify config exists in etcd
docker exec etcd-lab4 etcdctl get /monitor/config/$(hostname)

# Check agent logs for watch errors
```

### No data in Analysis app
```bash
# Check if Kafka topics exist
docker exec kafka-lab4 kafka-topics --list --bootstrap-server localhost:9092

# Check server is producing to Kafka
docker exec kafka-lab4 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic monitoring-data \
  --from-beginning
```

---

## 📦 Directory Structure

```
lab4/
├── README.md
├── docker-compose.yml          # Docker services configuration
├── requirements.txt            # Python dependencies
├── setup.sh                    # Setup script
├── start_docker.sh             # Start Docker services
├── start_server.sh             # Start gRPC server
├── start_agent.sh              # Start monitoring agent
├── start_analysis.sh           # Start analysis application
├── proto/
│   └── monitoring.proto        # gRPC service definition
├── plugins/
│   ├── __init__.py
│   ├── base.py                 # Plugin base class
│   ├── duplicate_filter.py     # Duplicate filter plugin
│   ├── threshold_alert.py      # Threshold alert plugin
│   └── logger.py               # Logger plugin
├── agent/
│   └── agent.py                # Monitoring agent with plugins
├── server/
│   ├── server.py               # gRPC server with Kafka
│   └── result.txt              # Logged monitoring data
└── analysis/
    └── analysis.py             # Analysis application
```

---

## ✅ Testing Checklist

- [ ] Docker services start successfully
- [ ] Server connects to etcd and Kafka
- [ ] Agent connects to server and etcd
- [ ] Agent sends metrics to server
- [ ] Server forwards data to Kafka
- [ ] Analysis app receives data from Kafka
- [ ] Analysis app can send commands via Kafka
- [ ] Server forwards commands to agent
- [ ] Agent executes commands
- [ ] Configuration updates from etcd
- [ ] Plugins load dynamically
- [ ] Duplicate filter works correctly
- [ ] Threshold alerts trigger correctly
- [ ] Multi-node setup works

---

## 🎓 Key Features

✅ **Plugin Architecture**: Dynamic plugin loading from etcd
✅ **Kafka Integration**: Streaming data and command pipeline
✅ **Real-time Configuration**: etcd-based dynamic config updates
✅ **Bidirectional gRPC**: Full-duplex communication
✅ **Health Monitoring**: etcd heartbeat tracking
✅ **Scalable**: Multi-node distributed deployment
✅ **Extensible**: Easy to add custom plugins

---

## 📝 Notes

- All configuration changes take effect immediately without restarting agents
- Plugins can be added/removed/reconfigured via etcd
- The system supports multiple agents on different nodes
- Kafka provides reliable message delivery and replay capability
- Use Docker logs to debug service issues

---

## 🆘 Support

For issues or questions:
1. Check Docker service logs: `docker-compose logs -f`
2. Verify network connectivity between components
3. Ensure all required ports are available
4. Check Python virtual environment is activated

---

**Happy Monitoring! 🎉**
