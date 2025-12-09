#!/usr/bin/env python3
"""
Lab 4 Analysis Application

Features:
- Consumes monitoring data from Kafka
- Prints data to stdout
- Sends commands to Kafka (forwarded to agents by gRPC server)
- Interactive command interface
"""

import json
import logging
import threading
import time
import sys
from datetime import datetime
from collections import defaultdict
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnalysisApplication:
    """
    Analysis application that consumes monitoring data from Kafka
    and can send commands back to agents
    """

    def __init__(self, kafka_bootstrap_servers='localhost:9092'):
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.kafka_topics = {
            'data': 'monitoring-data',
            'commands': 'monitoring-commands'
        }

        self.consumer = None
        self.producer = None
        self.running = True

        # Statistics
        self.stats = defaultdict(lambda: defaultdict(list))
        self.message_count = 0
        self.stats_lock = threading.Lock()

        self._connect_kafka()

    def _connect_kafka(self):
        """Connect to Kafka"""
        try:
            # Create consumer for monitoring data
            self.consumer = KafkaConsumer(
                self.kafka_topics['data'],
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='analysis-app-group'
            )
            logger.info(f"✓ Kafka consumer connected to topic: {self.kafka_topics['data']}")

            # Create producer for commands
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
            logger.info(f"✓ Kafka producer connected")

        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise

    def consume_data(self):
        """Consume monitoring data from Kafka and print to stdout"""
        logger.info(f"📊 Starting data consumption from Kafka...")

        try:
            for message in self.consumer:
                if not self.running:
                    break

                try:
                    data = message.value
                    self.message_count += 1

                    # Print to stdout
                    timestamp = datetime.fromtimestamp(data['timestamp'])
                    print(f"\n[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"Message #{self.message_count}")
                    print(f"  Client: {data['client_id']}")
                    print(f"  Hostname: {data['hostname']}")
                    print(f"  Metric: {data['metric']}")
                    print(f"  Value: {data['value']:.2f}")

                    # Update statistics
                    with self.stats_lock:
                        client_id = data['client_id']
                        metric = data['metric']
                        self.stats[client_id][metric].append(data['value'])

                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            logger.info("Data consumer stopped")

    def send_command(self, target: str, command_type: str, command_data: str = ""):
        """
        Send command to Kafka (will be forwarded to agents by gRPC server)
        Args:
            target: Target client ID or 'all'
            command_type: Type of command (e.g., 'status', 'get_config')
            command_data: Additional command data
        """
        try:
            command = {
                'command_id': f"analysis_cmd_{int(time.time())}",
                'target': target,
                'command_type': command_type,
                'command_data': command_data,
                'timestamp': int(time.time())
            }

            future = self.producer.send(self.kafka_topics['commands'], command)
            future.get(timeout=10)

            logger.info(f"✓ Command sent to Kafka: {command_type} -> {target}")
            print(f"\n✓ Command sent: {command_type} to {target}")

        except KafkaError as e:
            logger.error(f"Failed to send command: {e}")
            print(f"\n❌ Failed to send command: {e}")
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            print(f"\n❌ Error: {e}")

    def show_statistics(self):
        """Show aggregated statistics"""
        with self.stats_lock:
            if not self.stats:
                print("\n📊 No statistics available yet.")
                return

            print("\n" + "="*70)
            print("MONITORING STATISTICS")
            print("="*70)
            print(f"Total messages consumed: {self.message_count}\n")

            for client_id, metrics in self.stats.items():
                print(f"\n📍 Client: {client_id}")
                print("-" * 70)

                for metric, values in metrics.items():
                    if values:
                        avg_value = sum(values) / len(values)
                        min_value = min(values)
                        max_value = max(values)
                        count = len(values)

                        print(f"  {metric:15s}: "
                              f"count={count:4d}, "
                              f"avg={avg_value:7.2f}, "
                              f"min={min_value:7.2f}, "
                              f"max={max_value:7.2f}")

            print("="*70)

    def command_input_loop(self):
        """Interactive command input"""
        print("\n" + "="*60)
        print("  Analysis Application - Command Interface")
        print("="*60)
        print("  Available commands:")
        print("    help                       - Show this help")
        print("    stats                      - Show statistics")
        print("    send <target> <command>    - Send command to agent")
        print("                                 Example: send all status")
        print("    quit                       - Exit application")
        print("="*60)
        print()

        while self.running:
            try:
                cmd_input = input("Analysis> ").strip()

                if not cmd_input:
                    continue

                if cmd_input == 'help':
                    self._show_help()

                elif cmd_input == 'stats':
                    self.show_statistics()

                elif cmd_input.startswith('send '):
                    parts = cmd_input.split(' ', 2)
                    if len(parts) >= 3:
                        _, target, command_type = parts
                        self.send_command(target, command_type)
                    else:
                        print("❌ Usage: send <target> <command>")
                        print("   Example: send all status")

                elif cmd_input == 'quit':
                    print("\nShutting down...")
                    self.running = False
                    break

                else:
                    print("Unknown command. Type 'help' for available commands.")

            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n\nShutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error processing command: {e}")

    def _show_help(self):
        """Show help message"""
        print("\n" + "="*60)
        print("Available Commands:")
        print("="*60)
        print("  help                       - Show this help message")
        print("  stats                      - Show monitoring statistics")
        print("  send <target> <command>    - Send command to agent(s)")
        print("                               target: client_id or 'all'")
        print("                               command: status, get_config, etc.")
        print("  quit                       - Exit the application")
        print("="*60)
        print("\nExamples:")
        print("  send all status           - Send status command to all agents")
        print("  send my-agent status      - Send status to specific agent")
        print("="*60)

    def start(self):
        """Start the analysis application"""
        print("\n" + "="*60)
        print("  🔍 Lab 4 Analysis Application")
        print("="*60)
        print(f"  Kafka: {self.kafka_bootstrap_servers}")
        print(f"  Data Topic: {self.kafka_topics['data']}")
        print(f"  Command Topic: {self.kafka_topics['commands']}")
        print(f"  Status: Active")
        print("="*60)

        # Start consumer thread
        consumer_thread = threading.Thread(target=self.consume_data, daemon=True)
        consumer_thread.start()
        logger.info("✓ Consumer thread started")

        # Run command input loop in main thread
        try:
            self.command_input_loop()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        self.running = False

        if self.consumer:
            try:
                self.consumer.close()
                logger.info("✓ Consumer closed")
            except:
                pass

        if self.producer:
            try:
                self.producer.close()
                logger.info("✓ Producer closed")
            except:
                pass

        logger.info("Analysis application stopped")


def main():
    kafka_servers = 'localhost:9092'

    if len(sys.argv) > 1:
        kafka_servers = sys.argv[1]

    try:
        app = AnalysisApplication(kafka_bootstrap_servers=kafka_servers)
        app.start()
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
