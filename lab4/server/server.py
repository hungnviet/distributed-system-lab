import grpc
from concurrent import futures
import time
import logging
import threading
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import sys

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

    def __init__(self,
                 result_file='result.txt',
                 etcd_host='localhost',
                 etcd_port=2379,
                 kafka_bootstrap_servers='localhost:9092'):

        # gRPC client management
        self.clients = {}
        self.client_data = defaultdict(list)
        self.command_queue = defaultdict(list)
        self.lock = threading.Lock()

        # etcd configuration
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port
        self.etcd = None

        # Kafka configuration
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.kafka_producer = None
        self.kafka_consumer = None
        self.kafka_topics = {
            'data': 'monitoring-data',
            'commands': 'monitoring-commands'
        }

        # Node health tracking
        self.node_health = {}
        self.health_lock = threading.Lock()

        # Result file
        self.result_file = result_file

        # Watch IDs
        self.heartbeat_watch_id = None

        # Initialize
        self._init_result_file()
        self._connect_etcd()
        self._connect_kafka()
        self._start_kafka_consumer_thread()
        self._start_heartbeat_monitor()
        self._start_command_input()
        self._start_health_display()

    def _init_result_file(self):
        with open(self.result_file, 'w') as f:
            f.write(f"=== Lab 4 Monitoring Server Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        logger.info(f"Writing monitoring data to: {self.result_file}")

    def _connect_etcd(self):
        try:
            self.etcd = etcd3.client(host=self.etcd_host, port=self.etcd_port)
            logger.info(f"✓ Connected to etcd at {self.etcd_host}:{self.etcd_port}")
        except Exception as e:
            logger.error(f"Failed to connect to etcd: {e}")
            raise

    def _connect_kafka(self):
        """Connect to Kafka and create producer"""
        try:
            # Create Kafka producer
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
            logger.info(f"✓ Connected to Kafka at {self.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            logger.warning("Server will continue without Kafka integration")
            self.kafka_producer = None

    def _start_kafka_consumer_thread(self):
        """Start thread to consume commands from Kafka"""
        if not self.kafka_producer:
            logger.warning("Kafka not available, skipping command consumer")
            return

        consumer_thread = threading.Thread(
            target=self._consume_kafka_commands,
            daemon=True
        )
        consumer_thread.start()
        logger.info("✓ Started Kafka command consumer thread")

    def _consume_kafka_commands(self):
        """Consume commands from Kafka and queue them for agents"""
        try:
            consumer = KafkaConsumer(
                self.kafka_topics['commands'],
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='grpc-server-group'
            )

            logger.info(f"✓ Kafka consumer ready for topic: {self.kafka_topics['commands']}")

            for message in consumer:
                try:
                    command_data = message.value
                    logger.info(f"📥 Received command from Kafka: {command_data}")

                    # Create gRPC command
                    command = monitoring_pb2.Command(
                        command_id=command_data.get('command_id', f"cmd_{int(time.time())}"),
                        command_type=command_data.get('command_type', ''),
                        command_data=command_data.get('command_data', ''),
                        timestamp=command_data.get('timestamp', int(time.time()))
                    )

                    # Queue command for target agent
                    target = command_data.get('target', 'all')

                    with self.lock:
                        if target == 'all':
                            for client_id in self.clients.keys():
                                self.command_queue[client_id].append(command)
                            logger.info(f"✓ Queued command for {len(self.clients)} clients")
                        else:
                            if target in self.clients:
                                self.command_queue[target].append(command)
                                logger.info(f"✓ Queued command for {target}")
                            else:
                                logger.warning(f"Target client not found: {target}")

                except Exception as e:
                    logger.error(f"Error processing Kafka command: {e}")

        except Exception as e:
            logger.error(f"Kafka consumer error: {e}")

    def _send_to_kafka(self, topic: str, data: dict):
        """Send data to Kafka topic"""
        if not self.kafka_producer:
            return

        try:
            future = self.kafka_producer.send(topic, data)
            future.get(timeout=10)
            logger.debug(f"✓ Sent to Kafka topic '{topic}'")
        except KafkaError as e:
            logger.error(f"Failed to send to Kafka: {e}")
        except Exception as e:
            logger.error(f"Error sending to Kafka: {e}")

    def _start_heartbeat_monitor(self):
        try:
            self.heartbeat_watch_id = self.etcd.add_watch_prefix_callback(
                "/monitor/heartbeat/",
                self._on_heartbeat_event
            )
            logger.info("✓ Started heartbeat monitoring from etcd")
        except Exception as e:
            logger.error(f"Failed to start heartbeat monitor: {e}")

    def _on_heartbeat_event(self, watch_response):
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
                        logger.debug(f"[+] Node {hostname} heartbeat received")

                    except Exception as e:
                        logger.error(f"Error parsing heartbeat: {e}")

                elif isinstance(event, etcd3.events.DeleteEvent):
                    if hostname in self.node_health:
                        self.node_health[hostname]['status'] = 'DEAD'
                        self.node_health[hostname]['last_seen'] = datetime.now()
                    logger.warning(f"[-] Node {hostname} dead (key removed)")

    def _start_health_display(self):
        def display_health():
            while True:
                time.sleep(60)
                self.display_system_health()

        health_thread = threading.Thread(target=display_health, daemon=True)
        health_thread.start()

    def display_system_health(self):
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

                metrics = defaultdict(list)
                for data in data_list[-10:]:
                    metrics[data['metric']].append(data['value'])

                for metric, values in metrics.items():
                    avg_value = sum(values) / len(values)
                    min_value = min(values)
                    max_value = max(values)
                    print(f"   {metric:15s}: avg={avg_value:6.2f}, "
                          f"min={min_value:6.2f}, max={max_value:6.2f}")

            print("="*60)

    def _update_config(self, cmd_input):
        try:
            parts = cmd_input.split(' ', 2)
            if len(parts) < 3:
                print("❌ Usage: config <hostname> <json>")
                print("   Example: config myhost '{\"interval\": 10, \"metrics\": [\"cpu\"]}'")
                return

            _, hostname, config_json = parts

            config = json.loads(config_json)

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
        client_id = None
        hostname = None

        def response_generator():
            nonlocal client_id

            try:
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
                        if client_id in self.clients:
                            self.clients[client_id]['last_seen'] = datetime.now()

                    # Write to result.txt
                    log_entry = (f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                               f"Client: {client_id} | "
                               f"Hostname: {monitoring_data.hostname} | "
                               f"Metric: {monitoring_data.metric} | "
                               f"Value: {monitoring_data.value:.2f}\n")

                    with open(self.result_file, 'a') as f:
                        f.write(log_entry)

                    # Forward to Kafka
                    kafka_data = {
                        'timestamp': monitoring_data.timestamp,
                        'client_id': client_id,
                        'hostname': monitoring_data.hostname,
                        'metric': monitoring_data.metric,
                        'value': monitoring_data.value
                    }
                    self._send_to_kafka(self.kafka_topics['data'], kafka_data)

                    # Check for pending commands
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


def serve(port=50052, etcd_host='localhost', etcd_port=2379, kafka_servers='localhost:9092'):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    monitoring_service = MonitoringServer(
        etcd_host=etcd_host,
        etcd_port=etcd_port,
        kafka_bootstrap_servers=kafka_servers
    )

    monitoring_pb2_grpc.add_MonitoringServiceServicer_to_server(
        monitoring_service, server
    )

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    print("\n" + "="*60)
    print("  🖥️  Lab 4 Monitoring Server (Kafka-Integrated)")
    print("="*60)
    print(f"  gRPC Port: {port}")
    print(f"  etcd: {etcd_host}:{etcd_port}")
    print(f"  Kafka: {kafka_servers}")
    print(f"  Status: Ready to accept connections")
    print("="*60)
    print("\nForwarding data to Kafka...")
    print("Type 'help' for available commands\n")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        server.stop(0)


if __name__ == '__main__':
    port = 50052
    etcd_host = 'localhost'
    etcd_port = 2379
    kafka_servers = 'localhost:9092'

    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    if len(sys.argv) > 2:
        etcd_host = sys.argv[2]
    if len(sys.argv) > 3:
        kafka_servers = sys.argv[3]

    serve(port=port, etcd_host=etcd_host, etcd_port=etcd_port, kafka_servers=kafka_servers)
