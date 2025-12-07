import grpc
from concurrent import futures
import time
import logging
import threading
from datetime import datetime
from collections import defaultdict

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
    """Monitoring server that collects data and sends commands"""
    
    def __init__(self, result_file='result.txt'):
        self.clients = {}  # Store active client streams {client_id: stream}
        self.client_data = defaultdict(list)  # Store monitoring data
        self.command_queue = defaultdict(list)  # Commands waiting to be sent
        self.lock = threading.Lock()
        self.result_file = result_file
        
        # Clear/create result file
        with open(self.result_file, 'w') as f:
            f.write(f"=== Monitoring Server Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        
        logger.info(f"Writing monitoring data to: {self.result_file}")
        
        # Start command input thread
        self.command_thread = threading.Thread(target=self._command_input_loop, daemon=True)
        self.command_thread.start()
        
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
                        logger.info(f"✓ Client connected: {client_id} ({hostname})")
                    
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
                    logger.info(f"✗ Client disconnected: {client_id}")
        
        return response_generator()
    
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
                elif cmd_input == 'stats':
                    self._show_stats()
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
        print("\n" + "="*60)
        print("Available Commands:")
        print("="*60)
        print("  help                    - Show this help message")
        print("  list                    - List connected clients")
        print("  stats                   - Show monitoring statistics")
        print("  send <client_id> <cmd>  - Send command to specific client")
        print("                            Example: send debian-01 get_cpu")
        print("  send all <cmd>          - Send command to all clients")
        print("                            Example: send all status")
        print("  quit                    - Shutdown the server")
        print("\nAvailable command types:")
        print("  status       - Get client status")
        print("  get_cpu      - Request CPU usage")
        print("  get_memory   - Request memory usage")
        print("  get_disk     - Request disk usage")
        print("  execute:<cmd> - Execute shell command (e.g., execute:uptime)")
        print("="*60)
    
    def _list_clients(self):
        """List all connected clients"""
        with self.lock:
            if not self.clients:
                print("\n📋 No clients connected.")
                return
            
            print("\n" + "="*60)
            print("Connected Clients:")
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


def serve(port=50052):
    """Start the monitoring server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    monitoring_service = MonitoringServer()
    
    monitoring_pb2_grpc.add_MonitoringServiceServicer_to_server(
        monitoring_service, server
    )
    
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    print("\n" + "="*60)
    print("  🖥️  Monitoring Server Started")
    print("="*60)
    print(f"  Port: {port}")
    print(f"  Status: Ready to accept client connections")
    print("="*60)
    logger.info(f"Server listening on port {port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        server.stop(0)


if __name__ == '__main__':
    serve()
