#!/usr/bin/env python3
"""
Lab 3 Monitoring Server with etcd Integration

Features:
- Monitors heartbeats from all agents via etcd
- Maintains global view of system health (alive/dead nodes)
- Manages and pushes configuration to agents via etcd
- Receives monitoring data from agents via gRPC
"""

import grpc
from concurrent import futures
import time
import logging
import threading
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, Set

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


class MonitoringServer(monitoring_pb2_grpc.MonitoringServiceServicer):
    """Monitoring server with etcd heartbeat monitoring"""

    def __init__(self,
                 result_file='result.txt',
                 etcd_host='localhost',
                 etcd_port=2379):

        # gRPC client management
        self.clients = {}  # {client_id: info}
        self.client_data = defaultdict(list)
        self.command_queue = defaultdict(list)
        self.lock = threading.Lock()

        # etcd configuration
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port
        self.etcd = None

        # Node health tracking from etcd heartbeats
        self.node_health = {}  # {hostname: {status, last_seen, client_id}}
        self.health_lock = threading.Lock()

        # Result file
        self.result_file = result_file

        # Watch IDs
        self.heartbeat_watch_id = None

        # Initialize
        self._init_result_file()
        self._connect_etcd()
        self._start_heartbeat_monitor()
        self._start_command_input()
        self._start_health_display()

    def _init_result_file(self):
        """Initialize result file"""
        with open(self.result_file, 'w') as f:
            f.write(f"=== Monitoring Server Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        logger.info(f"Writing monitoring data to: {self.result_file}")

    def _connect_etcd(self):
        """Connect to etcd"""
        try:
            self.etcd = etcd3.client(host=self.etcd_host, port=self.etcd_port)
            logger.info(f"✓ Connected to etcd at {self.etcd_host}:{self.etcd_port}")
        except Exception as e:
            logger.error(f"Failed to connect to etcd: {e}")
            raise

    def _start_heartbeat_monitor(self):
        """Start monitoring heartbeats from etcd"""
        try:
            self.heartbeat_watch_id = self.etcd.add_watch_prefix_callback(
                "/monitor/heartbeat/",
                self._on_heartbeat_event
            )
            logger.info("✓ Started heartbeat monitoring from etcd")
        except Exception as e:
            logger.error(f"Failed to start heartbeat monitor: {e}")

    def _on_heartbeat_event(self, watch_response):
        """Callback for heartbeat events from etcd"""
        for event in watch_response.events:
            key = event.key.decode('utf-8')
            hostname = key.split('/')[-1]

            with self.health_lock:
                if isinstance(event, etcd3.events.PutEvent):
                    try:
                        value = json.loads(event.value.decode('utf-8'))
                        self.node_health[hostname] = {
                            'status': 'ALIVE',
                            'last_seen': datetime.now(),
                            'timestamp': value.get('ts', time.time()),
                            'client_id': value.get('client_id', hostname)
                        }
                        logger.info(f"[+] Node {hostname} alive -> {value}")

                    except Exception as e:
                        logger.error(f"Error parsing heartbeat: {e}")

                elif isinstance(event, etcd3.events.DeleteEvent):
                    if hostname in self.node_health:
                        self.node_health[hostname]['status'] = 'DEAD'
                        self.node_health[hostname]['last_seen'] = datetime.now()
                    logger.warning(f"[-] Node {hostname} dead (key removed)")

    def _start_health_display(self):
        """Start thread to periodically display system health"""
        def display_health():
            while True:
                time.sleep(15)  # Display every 15 seconds
                self.display_system_health()

        health_thread = threading.Thread(target=display_health, daemon=True)
        health_thread.start()

    def display_system_health(self):
        """Display global view of system health"""
        with self.health_lock:
            if not self.node_health:
                return

            print("\n" + "="*80)
            print("SYSTEM HEALTH - Global View")
            print("="*80)
            print(f"{'Hostname':<20} {'Status':<10} {'Client ID':<25} {'Last Seen':<20}")
            print("-"*80)

            for hostname, info in sorted(self.node_health.items()):
                status = info['status']
                client_id = info.get('client_id', 'N/A')
                last_seen = info['last_seen'].strftime('%Y-%m-%d %H:%M:%S')

                # Color-code status
                status_symbol = "✓" if status == "ALIVE" else "✗"

                print(f"{hostname:<20} {status_symbol} {status:<8} {client_id:<25} {last_seen:<20}")

            alive_count = sum(1 for n in self.node_health.values() if n['status'] == 'ALIVE')
            dead_count = sum(1 for n in self.node_health.values() if n['status'] == 'DEAD')

            print("-"*80)
            print(f"Total: {len(self.node_health)} nodes | Alive: {alive_count} | Dead: {dead_count}")
            print("="*80)

    def _start_command_input(self):
        """Start command input thread"""
        command_thread = threading.Thread(target=self._command_input_loop, daemon=True)
        command_thread.start()

    def _command_input_loop(self):
        """Background thread to accept commands from console"""
        logger.info("📝 Command input ready. Type 'help' for available commands.")

        while True:
            try:
                cmd_input = input("\nServer> ").strip()

                if not cmd_input:
                    continue

                if cmd_input == 'help':
                    self._show_help()
                elif cmd_input == 'list':
                    self._list_clients()
                elif cmd_input == 'health':
                    self.display_system_health()
                elif cmd_input == 'stats':
                    self._show_stats()
                elif cmd_input.startswith('config '):
                    self._update_config(cmd_input)
                elif cmd_input.startswith('send '):
                    self._parse_and_send_command(cmd_input)
                elif cmd_input == 'quit':
                    logger.info("Shutting down server...")
                    break
                else:
                    print("Unknown command. Type 'help' for available commands.")

            except EOFError:
                break
            except Exception as e:
                logger.error(f"Error processing command: {e}")

    def _show_help(self):
        """Display available commands"""
        print("\n" + "="*70)
        print("Available Commands:")
        print("="*70)
        print("  help                        - Show this help message")
        print("  list                        - List connected gRPC clients")
        print("  health                      - Show system health (all nodes)")
        print("  stats                       - Show monitoring statistics")
        print("  config <host> <json>        - Update agent configuration")
        print("                                Example: config myhost '{\"interval\": 10}'")
        print("  send <client_id> <cmd>      - Send command to specific client")
        print("  quit                        - Shutdown the server")
        print("="*70)

    def _list_clients(self):
        """List all connected gRPC clients"""
        with self.lock:
            if not self.clients:
                print("\n📋 No gRPC clients connected.")
                return

            print("\n" + "="*60)
            print("Connected gRPC Clients:")
            print("="*60)
            for client_id, client_info in self.clients.items():
                hostname = client_info.get('hostname', 'Unknown')
                last_seen = client_info.get('last_seen', datetime.now())
                print(f"  • {client_id} ({hostname}) - "
                      f"Last seen: {last_seen.strftime('%H:%M:%S')}")
            print("="*60)

    def _show_stats(self):
        """Show monitoring statistics"""
        with self.lock:
            if not self.client_data:
                print("\n📊 No monitoring data collected yet.")
                return

            print("\n" + "="*60)
            print("Monitoring Statistics:")
            print("="*60)

            for client_id, data_list in self.client_data.items():
                if not data_list:
                    continue

                print(f"\n📍 Client: {client_id}")

                # Group by metric
                metrics = defaultdict(list)
                for data in data_list[-10:]:  # Last 10 entries
                    metrics[data['metric']].append(data['value'])

                for metric, values in metrics.items():
                    avg_value = sum(values) / len(values)
                    min_value = min(values)
                    max_value = max(values)
                    print(f"   {metric:15s}: avg={avg_value:6.2f}, "
                          f"min={min_value:6.2f}, max={max_value:6.2f}")

            print("="*60)

    def _update_config(self, cmd_input):
        """Update agent configuration in etcd"""
        try:
            parts = cmd_input.split(' ', 2)
            if len(parts) < 3:
                print("❌ Usage: config <hostname> <json>")
                print("   Example: config myhost '{\"interval\": 10, \"metrics\": [\"cpu\", \"memory\"]}'")
                return

            _, hostname, config_json = parts

            # Parse and validate JSON
            config = json.loads(config_json)

            # Put to etcd
            config_key = f"/monitor/config/{hostname}"
            self.etcd.put(config_key, json.dumps(config))

            print(f"✓ Configuration updated for {hostname}")
            print(f"  Key: {config_key}")
            print(f"  Value: {json.dumps(config, indent=2)}")

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
        except Exception as e:
            print(f"❌ Error updating config: {e}")

    def _parse_and_send_command(self, cmd_input):
        """Parse and send command to client(s)"""
        parts = cmd_input.split(' ', 2)

        if len(parts) < 3:
            print("❌ Invalid command format. Use: send <client_id|all> <command>")
            return

        _, target, command_type = parts

        command = monitoring_pb2.Command(
            command_id=f"cmd_{int(time.time())}",
            command_type=command_type,
            command_data="",
            timestamp=int(time.time())
        )

        with self.lock:
            if target == 'all':
                if not self.clients:
                    print("❌ No clients connected.")
                    return

                for client_id in self.clients.keys():
                    self.command_queue[client_id].append(command)

                print(f"✓ Command '{command_type}' queued for {len(self.clients)} clients")
            else:
                if target not in self.clients:
                    print(f"❌ Client '{target}' not found. Use 'list' to see connected clients.")
                    return

                self.command_queue[target].append(command)
                print(f"✓ Command '{command_type}' queued for {target}")

    def MonitorStream(self, request_iterator, context):
        """
        Bidirectional streaming RPC
        Receives monitoring data from clients and sends commands back
        """
        client_id = None
        hostname = None

        def response_generator():
            """Generator for sending commands back to client"""
            nonlocal client_id

            try:
                # Process incoming monitoring data
                for monitoring_data in request_iterator:
                    if client_id is None:
                        client_id = monitoring_data.client_id
                        hostname = monitoring_data.hostname
                        with self.lock:
                            self.clients[client_id] = {
                                'context': context,
                                'hostname': hostname,
                                'last_seen': datetime.now()
                            }
                        logger.info(f"✓ gRPC Client connected: {client_id} ({hostname})")

                    # Store monitoring data
                    timestamp = datetime.fromtimestamp(monitoring_data.timestamp)
                    with self.lock:
                        self.client_data[client_id].append({
                            'timestamp': timestamp,
                            'hostname': monitoring_data.hostname,
                            'metric': monitoring_data.metric,
                            'value': monitoring_data.value
                        })
                        # Update last seen time
                        if client_id in self.clients:
                            self.clients[client_id]['last_seen'] = datetime.now()

                    # Write to result.txt file
                    log_entry = (f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                               f"Client: {client_id} | "
                               f"Hostname: {monitoring_data.hostname} | "
                               f"Metric: {monitoring_data.metric} | "
                               f"Value: {monitoring_data.value:.2f}\n")

                    with open(self.result_file, 'a') as f:
                        f.write(log_entry)

                    # Check if there are commands waiting for this client
                    with self.lock:
                        if client_id in self.command_queue and self.command_queue[client_id]:
                            command = self.command_queue[client_id].pop(0)
                            logger.info(f"📤 Sending command to {client_id}: {command.command_type}")
                            yield command

            except grpc.RpcError as e:
                logger.warning(f"Client {client_id} disconnected: {e.code()}")
            finally:
                if client_id:
                    with self.lock:
                        if client_id in self.clients:
                            del self.clients[client_id]
                    logger.info(f"✗ gRPC Client disconnected: {client_id}")

        return response_generator()


def serve(port=50052, etcd_host='localhost', etcd_port=2379):
    """Start the monitoring server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    monitoring_service = MonitoringServer(
        etcd_host=etcd_host,
        etcd_port=etcd_port
    )

    monitoring_pb2_grpc.add_MonitoringServiceServicer_to_server(
        monitoring_service, server
    )

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    print("\n" + "="*60)
    print("  🖥️  Lab 3 Monitoring Server with etcd")
    print("="*60)
    print(f"  gRPC Port: {port}")
    print(f"  etcd: {etcd_host}:{etcd_port}")
    print(f"  Status: Ready to accept connections")
    print("="*60)
    print("\nMonitoring heartbeats from etcd...")
    print("Type 'help' for available commands\n")
    logger.info(f"Server listening on port {port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        server.stop(0)


if __name__ == '__main__':
    import sys

    port = 50052
    etcd_host = 'localhost'
    etcd_port = 2379

    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    if len(sys.argv) > 2:
        etcd_host = sys.argv[2]

    serve(port=port, etcd_host=etcd_host, etcd_port=etcd_port)
