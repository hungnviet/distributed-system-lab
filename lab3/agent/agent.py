#!/usr/bin/env python3
"""
Lab 3 Monitoring Agent with etcd Integration

Features:
- Sends heartbeat to etcd with lease/TTL
- Watches configuration from etcd in real-time
- Thread-safe configuration access using RWLock
- Collects metrics based on dynamic configuration
- Sends metrics to gRPC server
"""

import grpc
import time
import platform
import psutil
import json
import logging
import threading
import sys
from datetime import datetime
from typing import Dict, List, Any

# Import etcd client
import etcd3
import etcd3.events

# Import generated protobuf classes
import monitoring_pb2
import monitoring_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RWLock:
    """Reader-Writer Lock for thread-safe configuration access"""

    def __init__(self):
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.RLock())
        self._write_ready = threading.Condition(threading.RLock())

    def acquire_read(self):
        """Acquire read lock"""
        self._read_ready.acquire()
        try:
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
        finally:
            self._read_ready.release()

    def release_read(self):
        """Release read lock"""
        self._read_ready.acquire()
        try:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notifyAll()
        finally:
            self._read_ready.release()

    def acquire_write(self):
        """Acquire write lock"""
        self._write_ready.acquire()
        self._writers += 1
        self._write_ready.release()

        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        """Release write lock"""
        self._writers -= 1
        self._read_ready.notifyAll()
        self._read_ready.release()
        self._write_ready.acquire()
        self._write_ready.notifyAll()
        self._write_ready.release()


class MonitoringAgent:
    """Monitoring Agent with etcd integration"""

    def __init__(self,
                 server_address='localhost:50052',
                 client_id=None,
                 etcd_host='localhost',
                 etcd_port=2379,
                 lease_ttl=10):

        self.server_address = server_address
        self.hostname = platform.node()
        self.client_id = client_id or f"{self.hostname}-{int(time.time())}"

        # etcd configuration
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port
        self.lease_ttl = lease_ttl

        # Configuration with thread-safe access
        self.config = {
            'interval': 5,
            'metrics': ['cpu', 'memory', 'disk', 'network']
        }
        self.config_lock = RWLock()

        # Agent state
        self.running = True
        self.etcd = None
        self.heartbeat_thread = None
        self.config_watch_id = None

        # Disk/Network I/O counters for calculating rates
        self.last_disk_io = None
        self.last_net_io = None
        self.last_io_time = None

        logger.info(f"Initializing agent: {self.client_id}")
        logger.info(f"Hostname: {self.hostname}")
        logger.info(f"Server: {self.server_address}")
        logger.info(f"etcd: {self.etcd_host}:{self.etcd_port}")

    def connect_etcd(self):
        """Connect to etcd server"""
        try:
            self.etcd = etcd3.client(host=self.etcd_host, port=self.etcd_port)
            logger.info("✓ Connected to etcd")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to etcd: {e}")
            return False

    def get_config(self) -> Dict[str, Any]:
        """Thread-safe config read"""
        self.config_lock.acquire_read()
        try:
            return self.config.copy()
        finally:
            self.config_lock.release_read()

    def update_config(self, new_config: Dict[str, Any]):
        """Thread-safe config write"""
        self.config_lock.acquire_write()
        try:
            self.config = new_config
            logger.info(f"✓ Configuration updated: {self.config}")
        finally:
            self.config_lock.release_write()

    def send_heartbeat(self):
        """Send heartbeat to etcd with lease/TTL"""
        heartbeat_key = f"/monitor/heartbeat/{self.hostname}"
        lease = self.etcd.lease(self.lease_ttl)

        logger.info(f"Heartbeat lease created with TTL {self.lease_ttl}s, ID: {lease.id}")

        try:
            while self.running:
                try:
                    data = json.dumps({
                        "status": "alive",
                        "ts": time.time(),
                        "client_id": self.client_id
                    })

                    self.etcd.put(heartbeat_key, data, lease=lease)
                    logger.debug(f"Heartbeat sent to {heartbeat_key}")

                    lease.refresh()

                    # Sleep less than TTL to ensure refresh before expiry
                    time.sleep(self.lease_ttl / 2)

                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")
                    time.sleep(1)

        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Stopping heartbeat...")
            try:
                lease.revoke()
            except:
                pass

    def watch_config(self, watch_response):
        """Callback for etcd config watch"""
        for event in watch_response.events:
            if isinstance(event, etcd3.events.PutEvent):
                try:
                    new_config = json.loads(event.value.decode('utf-8'))
                    logger.info(f"⚙️  Config change detected: {new_config}")
                    self.update_config(new_config)
                except Exception as e:
                    logger.error(f"Error parsing config: {e}")

    def load_and_watch_config(self):
        """Load initial config from etcd and watch for changes"""
        config_key = f"/monitor/config/{self.hostname}"

        try:
            # Load initial configuration
            value, _ = self.etcd.get(config_key)
            if value:
                initial_config = json.loads(value.decode('utf-8'))
                self.update_config(initial_config)
                logger.info(f"✓ Loaded initial config from etcd: {initial_config}")
            else:
                # Put default config to etcd if not exists
                default_config = self.get_config()
                self.etcd.put(config_key, json.dumps(default_config))
                logger.info(f"✓ Created default config in etcd: {default_config}")

            # Watch for configuration changes
            self.config_watch_id = self.etcd.add_watch_callback(
                config_key,
                self.watch_config
            )
            logger.info(f"✓ Watching config key: {config_key}")

        except Exception as e:
            logger.error(f"Error loading config from etcd: {e}")

    def collect_metrics(self) -> List[monitoring_pb2.MonitoringData]:
        """Collect system metrics based on configuration"""
        config = self.get_config()
        metrics_to_collect = config.get('metrics', ['cpu', 'memory'])

        metrics = []
        timestamp = int(time.time())

        for metric_name in metrics_to_collect:
            metric_name = metric_name.lower().strip()

            try:
                if metric_name == 'cpu':
                    value = psutil.cpu_percent(interval=0.1)
                    metrics.append(self._create_metric('cpu', value, timestamp))

                elif metric_name == 'memory':
                    memory = psutil.virtual_memory()
                    metrics.append(self._create_metric('memory', memory.percent, timestamp))

                elif metric_name == 'disk':
                    disk = psutil.disk_usage('/')
                    metrics.append(self._create_metric('disk', disk.percent, timestamp))

                elif metric_name in ['disk read', 'disk write']:
                    disk_metrics = self._get_disk_io_rate()
                    if disk_metrics:
                        if metric_name == 'disk read':
                            metrics.append(self._create_metric('disk_read', disk_metrics['read'], timestamp))
                        else:
                            metrics.append(self._create_metric('disk_write', disk_metrics['write'], timestamp))

                elif metric_name in ['net in', 'net out', 'network']:
                    net_metrics = self._get_network_io_rate()
                    if net_metrics:
                        if metric_name == 'net in':
                            metrics.append(self._create_metric('net_in', net_metrics['in'], timestamp))
                        elif metric_name == 'net out':
                            metrics.append(self._create_metric('net_out', net_metrics['out'], timestamp))
                        else:  # 'network'
                            metrics.append(self._create_metric('net_in', net_metrics['in'], timestamp))
                            metrics.append(self._create_metric('net_out', net_metrics['out'], timestamp))

            except Exception as e:
                logger.error(f"Error collecting metric '{metric_name}': {e}")

        return metrics

    def _create_metric(self, metric_name: str, value: float, timestamp: int):
        """Helper to create a metric message"""
        return monitoring_pb2.MonitoringData(
            timestamp=timestamp,
            hostname=self.hostname,
            metric=metric_name,
            value=value,
            client_id=self.client_id
        )

    def _get_disk_io_rate(self) -> Dict[str, float]:
        """Calculate disk I/O rate (bytes/sec)"""
        try:
            current_io = psutil.disk_io_counters()
            current_time = time.time()

            if self.last_disk_io and self.last_io_time:
                time_delta = current_time - self.last_io_time
                read_rate = (current_io.read_bytes - self.last_disk_io.read_bytes) / time_delta
                write_rate = (current_io.write_bytes - self.last_disk_io.write_bytes) / time_delta

                self.last_disk_io = current_io
                self.last_io_time = current_time

                return {
                    'read': read_rate / (1024 * 1024),  # Convert to MB/s
                    'write': write_rate / (1024 * 1024)
                }
            else:
                self.last_disk_io = current_io
                self.last_io_time = current_time
                return None
        except Exception as e:
            logger.error(f"Error getting disk I/O: {e}")
            return None

    def _get_network_io_rate(self) -> Dict[str, float]:
        """Calculate network I/O rate (bytes/sec)"""
        try:
            current_io = psutil.net_io_counters()
            current_time = time.time()

            if self.last_net_io and self.last_io_time:
                time_delta = current_time - self.last_io_time
                in_rate = (current_io.bytes_recv - self.last_net_io.bytes_recv) / time_delta
                out_rate = (current_io.bytes_sent - self.last_net_io.bytes_sent) / time_delta

                self.last_net_io = current_io

                return {
                    'in': in_rate / (1024 * 1024),  # Convert to MB/s
                    'out': out_rate / (1024 * 1024)
                }
            else:
                self.last_net_io = current_io
                if not self.last_io_time:
                    self.last_io_time = current_time
                return None
        except Exception as e:
            logger.error(f"Error getting network I/O: {e}")
            return None

    def execute_command(self, command):
        """Execute command received from server"""
        logger.info(f"📥 Received command: {command.command_type}")

        try:
            if command.command_type == 'status':
                output = self._get_status()
                logger.info(f"✓ Status check completed")
                return True, output

            elif command.command_type == 'get_config':
                config = self.get_config()
                output = f"Current config: {json.dumps(config, indent=2)}"
                logger.info(f"✓ Config check completed")
                return True, output

            else:
                logger.warning(f"Unknown command type: {command.command_type}")
                return False, f"Unknown command: {command.command_type}"

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return False, str(e)

    def _get_status(self):
        """Get system status"""
        config = self.get_config()
        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        status = f"""
System Status for {self.hostname}:
  CPU Usage: {cpu}%
  Memory Usage: {memory.percent}%
  Disk Usage: {disk.percent}%
  Platform: {platform.platform()}
  Config: interval={config.get('interval')}s, metrics={config.get('metrics')}
"""
        return status.strip()

    def generate_monitoring_stream(self, response_iterator):
        """Generator that yields monitoring data periodically"""
        while self.running:
            try:
                config = self.get_config()
                interval = config.get('interval', 5)

                # Collect and send metrics
                metrics = self.collect_metrics()
                for metric in metrics:
                    yield metric
                    logger.info(f"📤 Sent: {metric.metric} = {metric.value:.2f}")

                # Wait based on configured interval
                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring stream: {e}")
                time.sleep(1)

    def start(self):
        """Start the monitoring agent"""
        # Connect to etcd
        if not self.connect_etcd():
            logger.error("Cannot start without etcd connection")
            return

        # Load configuration and watch for changes
        self.load_and_watch_config()

        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(
            target=self.send_heartbeat,
            daemon=True
        )
        self.heartbeat_thread.start()
        logger.info("✓ Heartbeat thread started")

        # Connect to gRPC server
        logger.info(f"Connecting to gRPC server at {self.server_address}...")

        try:
            channel = grpc.insecure_channel(self.server_address)
            stub = monitoring_pb2_grpc.MonitoringServiceStub(channel)

            config = self.get_config()

            print("\n" + "="*60)
            print(f"  Lab 3 Monitoring Agent - {self.client_id}")
            print("="*60)
            print(f"  Hostname: {self.hostname}")
            print(f"  Server: {self.server_address}")
            print(f"  etcd: {self.etcd_host}:{self.etcd_port}")
            print(f"  Config: interval={config.get('interval')}s")
            print(f"  Metrics: {', '.join(config.get('metrics', []))}")
            print(f"  Status: Active - Config updates in real-time from etcd")
            print("="*60)
            print("\nPress Ctrl+C to stop\n")

            # Start bidirectional streaming
            response_iterator = stub.MonitorStream(
                self.generate_monitoring_stream(None)
            )

            # Listen for commands from server
            for command in response_iterator:
                success, output = self.execute_command(command)
                logger.info(f"Command output: {output}")

        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e.code()} - {e.details()}")
        except KeyboardInterrupt:
            logger.info("\nStopping agent...")
            self.running = False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        self.running = False

        if self.config_watch_id and self.etcd:
            try:
                self.etcd.cancel_watch(self.config_watch_id)
            except:
                pass

        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2)

        logger.info("Agent stopped")


def main():
    """Main entry point"""
    # Parse command line arguments
    server_address = 'localhost:50052'
    client_id = None
    etcd_host = 'localhost'
    etcd_port = 2379

    if len(sys.argv) > 1:
        server_address = sys.argv[1]
    if len(sys.argv) > 2:
        client_id = sys.argv[2]
    if len(sys.argv) > 3:
        etcd_host = sys.argv[3]

    agent = MonitoringAgent(
        server_address=server_address,
        client_id=client_id,
        etcd_host=etcd_host,
        etcd_port=etcd_port
    )
    agent.start()


if __name__ == '__main__':
    main()
