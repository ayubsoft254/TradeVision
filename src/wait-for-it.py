#!/usr/bin/env python3
import socket
import time
import sys

def wait_for_port(host, port, timeout=60):
    """Wait for a TCP port to be available"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(0.1)
    return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python wait-for-it.py <host> <port>")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2])
    
    print(f"Waiting for {host}:{port}...")
    if wait_for_port(host, port):
        print(f"{host}:{port} is ready!")
        sys.exit(0)
    else:
        print(f"Timeout waiting for {host}:{port}")
        sys.exit(1)

if __name__ == "__main__":
    main()