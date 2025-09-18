#!/bin/bash
# wait-for-it.sh - Wait for service to be ready

set -e

host="$1"
port="$2"
timeout="${3:-60}"

usage() {
    echo "Usage: $0 host port [timeout]" >&2
    echo "  host     - hostname or IP address" >&2
    echo "  port     - port number" >&2
    echo "  timeout  - timeout in seconds (default: 60)" >&2
    exit 1
}

if [ -z "$host" ] || [ -z "$port" ]; then
    usage
fi

echo "Waiting up to $timeout seconds for $host:$port..."

start_time=$(date +%s)
while true; do
    if nc -z "$host" "$port" >/dev/null 2>&1; then
        end_time=$(date +%s)
        elapsed_time=$((end_time - start_time))
        echo "$host:$port is available after $elapsed_time seconds"
        exit 0
    fi
    
    current_time=$(date +%s)
    elapsed_time=$((current_time - start_time))
    
    if [ $elapsed_time -ge $timeout ]; then
        echo "Timeout waiting for $host:$port after $elapsed_time seconds" >&2
        exit 1
    fi
    
    sleep 1
done