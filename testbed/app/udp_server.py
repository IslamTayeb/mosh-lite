#!/usr/bin/env python3
"""
UDP Server - Receives packets and sends responses back to client
"""

import socket
import json
import time
import sys
import signal
from datetime import datetime

# Configuration
UDP_IP = "0.0.0.0"  # Listen on all interfaces
UDP_PORT = 5000
LOG_FILE = "/var/log/udp_server.log"
STATS_FILE = "/artifacts/server_stats.json"

# Statistics
stats = {
    "packets_received": 0,
    "packets_sent": 0,
    "start_time": None,
    "end_time": None,
    "errors": 0
}

def log(message):
    """Log message with timestamp"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end='')
    sys.stdout.flush()
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_line)
    except Exception as e:
        print(f"Error writing to log: {e}", file=sys.stderr)

def save_stats():
    """Save statistics to file"""
    stats["end_time"] = datetime.utcnow().isoformat() + "Z"
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
        log(f"Statistics saved to {STATS_FILE}")
    except Exception as e:
        log(f"Error saving statistics: {e}")

def signal_handler(sig, frame):
    """Handle shutdown signal"""
    log("Received shutdown signal")
    save_stats()
    log(f"Server statistics - Received: {stats['packets_received']}, Sent: {stats['packets_sent']}, Errors: {stats['errors']}")
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))

    stats["start_time"] = datetime.utcnow().isoformat() + "Z"
    log(f"UDP Server listening on {UDP_IP}:{UDP_PORT}")

    while True:
        try:
            # Receive packet
            data, client_addr = sock.recvfrom(4096)
            recv_time = time.time()

            try:
                # Decode packet
                packet = json.loads(data.decode('utf-8'))
                seq = packet.get('seq', -1)
                client_send_time = packet.get('timestamp', 0)

                stats["packets_received"] += 1

                # Log every 100th packet to avoid flooding logs
                if seq % 100 == 0 or seq < 10:
                    log(f"RECV seq={seq} from {client_addr[0]}:{client_addr[1]}")

                # Prepare response
                response = {
                    "seq": seq,
                    "client_send_time": client_send_time,
                    "server_recv_time": recv_time,
                    "server_send_time": time.time()
                }

                # Send response back to client
                response_data = json.dumps(response).encode('utf-8')
                sock.sendto(response_data, client_addr)
                stats["packets_sent"] += 1

            except json.JSONDecodeError as e:
                log(f"Error decoding packet from {client_addr}: {e}")
                stats["errors"] += 1
            except Exception as e:
                log(f"Error processing packet: {e}")
                stats["errors"] += 1

        except Exception as e:
            log(f"Socket error: {e}")
            stats["errors"] += 1
            time.sleep(0.1)  # Brief pause on error

if __name__ == "__main__":
    main()
