import grpc
import time
import platform
import psutil
import subprocess
import logging
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../server'))

import monitoring_pb2
import monitoring_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MacOSMonitoringClient:    
    def __init__(self, server_address='localhost:50052', client_id='macos-01'):
        self.server_address = server_address
        self.client_id = client_id
        self.hostname = platform.node()
        self.running = True
        
        logger.info(f"Initializing macOS client: {self.client_id}")
        logger.info(f"Hostname: {self.hostname}")
        logger.info(f"Platform: {platform.platform()}")
    
    def collect_metrics(self):
        """Collect system metrics (macOS-specific)"""
        metrics = []
        timestamp = int(time.time())
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append(monitoring_pb2.MonitoringData(
            timestamp=timestamp,
            hostname=self.hostname,
            metric='cpu_usage',
            value=cpu_percent,
            client_id=self.client_id
        ))
        
        # Memory usage
        memory = psutil.virtual_memory()
        metrics.append(monitoring_pb2.MonitoringData(
            timestamp=timestamp,
            hostname=self.hostname,
            metric='memory_usage',
            value=memory.percent,
            client_id=self.client_id
        ))
        
        # Disk usage
        disk = psutil.disk_usage('/')
        metrics.append(monitoring_pb2.MonitoringData(
            timestamp=timestamp,
            hostname=self.hostname,
            metric='disk_usage',
            value=disk.percent,
            client_id=self.client_id
        ))
        
        # Battery status (if laptop)
        try:
            battery = psutil.sensors_battery()
            if battery:
                metrics.append(monitoring_pb2.MonitoringData(
                    timestamp=timestamp,
                    hostname=self.hostname,
                    metric='battery_percent',
                    value=battery.percent,
                    client_id=self.client_id
                ))
        except:
            pass  # Battery not available
        
        # Load average (macOS specific)
        try:
            load_avg = os.getloadavg()[0]  # 1-minute load average
            metrics.append(monitoring_pb2.MonitoringData(
                timestamp=timestamp,
                hostname=self.hostname,
                metric='load_average',
                value=load_avg,
                client_id=self.client_id
            ))
        except:
            pass
        
        return metrics
    
    def execute_command(self, command):
        """Execute command received from server"""
        logger.info(f"📥 Received command: {command.command_type}")
        
        try:
            if command.command_type == 'status':
                output = self._get_status()
                logger.info(f"✓ Status check completed")
                return True, output
                
            elif command.command_type == 'get_cpu':
                cpu = psutil.cpu_percent(interval=1)
                output = f"CPU Usage: {cpu}%"
                logger.info(f"✓ CPU check: {cpu}%")
                return True, output
                
            elif command.command_type == 'get_memory':
                memory = psutil.virtual_memory()
                output = f"Memory Usage: {memory.percent}% ({memory.used / (1024**3):.2f}GB / {memory.total / (1024**3):.2f}GB)"
                logger.info(f"✓ Memory check: {memory.percent}%")
                return True, output
                
            elif command.command_type == 'get_disk':
                disk = psutil.disk_usage('/')
                output = f"Disk Usage: {disk.percent}% ({disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB)"
                logger.info(f"✓ Disk check: {disk.percent}%")
                return True, output
                
            elif command.command_type.startswith('execute:'):
                cmd = command.command_type.split(':', 1)[1]
                output = self._execute_shell_command(cmd)
                logger.info(f"✓ Executed: {cmd}")
                return True, output
                
            else:
                logger.warning(f"Unknown command type: {command.command_type}")
                return False, f"Unknown command: {command.command_type}"
                
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return False, str(e)
    
    def _get_status(self):
        """Get system status (macOS-specific)"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        status = f"""
System Status for {self.hostname} :
  CPU Usage: {cpu}%
  Memory Usage: {memory.percent}%
  Disk Usage: {disk.percent}%
  Uptime: {uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m
  Platform: {platform.platform()}
  macOS Version: {platform.mac_ver()[0]}
"""
        
        # Add battery info if available
        try:
            battery = psutil.sensors_battery()
            if battery:
                status += f"  Battery: {battery.percent}%"
                if battery.power_plugged:
                    status += " (Charging)"
                status += "\n"
        except:
            pass
        
        return status.strip()
    
    def _execute_shell_command(self, cmd):
        """Execute shell command safely"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Error: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "Error: Command timeout"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def generate_monitoring_stream(self, response_iterator):
        """Generator that yields monitoring data periodically"""
        while self.running:
            try:
                # Send monitoring metrics
                metrics = self.collect_metrics()
                for metric in metrics:
                    yield metric
                    logger.info(f"📤 Sent: {metric.metric} = {metric.value:.2f}")
                
                # Wait before next collection
                time.sleep(5)  # Send data every 5 seconds
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                time.sleep(5)
    
    def start(self):
        """Start the monitoring client"""
        logger.info(f"Connecting to server at {self.server_address}...")
        
        try:
            channel = grpc.insecure_channel(self.server_address)
            stub = monitoring_pb2_grpc.MonitoringServiceStub(channel)
            
            logger.info("✓ Connected to server")
            print("\n" + "="*60)
            print(f"  macOS Monitoring Client - {self.client_id}")
            print("="*60)
            print(f"  Hostname: {self.hostname}")
            print(f"  Server: {self.server_address}")
            print(f"  Status: Active - Sending metrics every 5 seconds")
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
            logger.error(f"Connection error: {e.code()} - {e.details()}")
        except KeyboardInterrupt:
            logger.info("\nStopping client...")
            self.running = False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            logger.info("Client stopped")


if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    server_address = 'localhost:50052'
    client_id = 'default client'
    
    if len(sys.argv) > 1:
        server_address = sys.argv[1]
    if len(sys.argv) > 2:
        client_id = sys.argv[2]
    
    client = MacOSMonitoringClient(server_address, client_id)
    client.start()