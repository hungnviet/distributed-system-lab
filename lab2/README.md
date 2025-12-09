Step By Step

Terminal 1 - Server:
cd lab2/server
./setup_monitoring.sh
./start_monitoring_server.sh

list : to show the list of connection
send <client id> <cmd>

Terminal 2 - macOS Client:
cd lab2/client
source ../server/venv/bin/activate
python macos-client.py <server addres> <client id>

10.128.21.53 : HCMUT01
