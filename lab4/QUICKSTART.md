# 🚀 Lab 4 Quick Start Guide

Follow these steps to get Lab 4 running in 5 minutes!

## Step 1: Initial Setup (One-time)

```bash
# Run the setup script
./setup.sh
```

This installs all dependencies and generates gRPC code.

---

## Step 2: Start Docker Services

```bash
# Start Kafka, Zookeeper, and etcd
./start_docker.sh

# Wait ~15 seconds for services to initialize
# Then test connections
./test_connection.sh
```

Expected output: All services should show ✅

---

## Step 3: Start the System (4 Terminals)

### Terminal 1: gRPC Server

```bash
cd /Users/macbookpro/Documents/uni-document/251/dis-sys/lab/lab4
./start_server.sh
```

Wait until you see: `Status: Ready to accept connections`

### Terminal 2: Monitoring Agent

```bash
cd /Users/macbookpro/Documents/uni-document/251/dis-sys/lab/lab4
./start_agent.sh
```

Wait until you see: `Status: Active`

### Terminal 3: Analysis Application

```bash
cd /Users/macbookpro/Documents/uni-document/251/dis-sys/lab/lab4
./start_analysis.sh
```

## Step 4: Test Plugin Architecture

### Enable Duplicate Filter Plugin

In **Terminal 1** (Server):

```bash
Server> config $(hostname) '{"interval": 3, "metrics": ["cpu", "memory"], "plugins": ["plugins.duplicate_filter.DuplicateFilterPlugin"]}'
```

config MiWiFi-R3-srv {"interval": 5, "metrics": ["cpu"], "plugins": ["plugins.duplicate_filter.DuplicateFilterPlugin"]}
config MacBook-Pro-2.local {"interval": 3, "metrics": ["net in", "net out"], "plugins": ["plugins.duplicate_filter.DuplicateFilterPlugin"]}

### Enable Alert Plugin with Custom Thresholds

In **Terminal 1** (Server):

```bash
Server> config $(hostname) {"interval": 2, "metrics": ["cpu", "memory"], "plugins": ["plugins.threshold_alert.ThresholdAlertPlugin"], "plugin_configs": {"ThresholdAlertPlugin": {"cpu": 50, "memory": 60}}}
```

config MacBook-Pro-2.local {"interval": 2, "metrics": ["cpu", "memory"], "plugins": ["plugins.threshold_alert.ThresholdAlertPlugin"], "plugin_configs": {"ThresholdAlertPlugin": {"cpu": 70, "memory": 80}}}

The agent will now alert when CPU > 50% or Memory > 60%

---

## Step 5: Test Command Flow

### Send Command from Analysis to Agent

In **Terminal 3** (Analysis):

```bash
Analysis> send all status
```

Watch the data flow:

1. **Terminal 3**: Command sent to Kafka
2. **Terminal 1**: Server receives command from Kafka
3. **Terminal 2**: Agent receives and executes command
4. **Terminal 1**: Server logs response

---

## Step 6: Monitor System

### View Server Commands

In **Terminal 1** (Server):

```bash
Server> help      # Show all commands
Server> list      # List connected agents
Server> health    # Show node health
Server> stats     # Show statistics
```

### View Analysis Commands

In **Terminal 3** (Analysis):

```bash
Analysis> help    # Show all commands
Analysis> stats   # Show aggregated statistics
```

---

## Configuration Examples

### High-frequency monitoring with all plugins

```bash
Server> config $(hostname) '{
  "interval": 1,
  "metrics": ["cpu", "memory", "disk", "net in", "net out"],
  "plugins": [
    "plugins.duplicate_filter.DuplicateFilterPlugin",
    "plugins.threshold_alert.ThresholdAlertPlugin",
    "plugins.logger.LoggerPlugin"
  ],
  "plugin_configs": {
    "ThresholdAlertPlugin": {"cpu": 80, "memory": 85, "disk": 90}
  }
}'
```

### Minimal monitoring (no plugins)

```bash
Server> config $(hostname) '{
  "interval": 10,
  "metrics": ["cpu"],
  "plugins": []
}'
```

---

## Verify Everything Works

### ✅ Checklist:

- [ ] Docker services running (`docker-compose ps`)
- [ ] Server shows "Ready to accept connections"
- [ ] Agent shows "Status: Active"
- [ ] Analysis app showing incoming data
- [ ] Can update config and see agent reload plugins
- [ ] Can send commands from Analysis app
- [ ] Agent receives and executes commands

---

## Common Issues

### "Connection refused" errors

```bash
# Check Docker services
docker-compose ps

# Restart if needed
docker-compose restart
```

### Agent not receiving config

```bash
# Check if config exists in etcd
docker exec etcd-lab4 etcdctl get /monitor/config/$(hostname)

# Manually set config
docker exec etcd-lab4 etcdctl put /monitor/config/$(hostname) \
  '{"interval": 5, "metrics": ["cpu", "memory"], "plugins": []}'
```

### No data in Analysis app

```bash
# Check Kafka topics
docker exec kafka-lab4 kafka-topics --list --bootstrap-server localhost:9092

# Should show: monitoring-data and monitoring-commands

# Check if data is flowing
docker exec kafka-lab4 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic monitoring-data \
  --from-beginning
```

---

## Stop Everything

### Stop applications

Press `Ctrl+C` in each terminal

### Stop Docker services

```bash
docker-compose down
```

---

## Next Steps

1. **Create custom plugins** - See `plugins/base.py` for the interface
2. **Multi-node setup** - See README.md for instructions
3. **Explore Kafka** - Try the Kafka commands in README.md
4. **Monitor etcd** - Check heartbeats and configs

---

**Enjoy Lab 4! 🎉**
