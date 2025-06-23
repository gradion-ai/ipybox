#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# Default ports for ipybox
EXECUTOR_PORT=8888
RESOURCE_PORT=8900
ALLOWED_DOMAINS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --executor-port)
            EXECUTOR_PORT="$2"
            shift 2
            ;;
        --resource-port)
            RESOURCE_PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [domain1|ip1 domain2|ip2 ...] [--executor-port PORT] [--resource-port PORT]"
            echo "  domain1, ip1, etc.: Allowed domain names or IPv4(/CIDR) addresses for internet access"
            echo "  --executor-port PORT: Executor port (default: 8888)"
            echo "  --resource-port PORT: Resource port (default: 8900)"
            exit 0
            ;;
        -*)
            echo "Unknown option $1"
            exit 1
            ;;
        *)
            ALLOWED_DOMAINS+=("$1")
            shift
            ;;
    esac
done

echo "Initializing firewall with executor port $EXECUTOR_PORT and resource port $RESOURCE_PORT"
echo "Allowed domains/IPs: ${ALLOWED_DOMAINS[*]}"

if ! command -v iptables &> /dev/null || ! command -v ipset &> /dev/null; then
    echo "ERROR: Required packages (iptables, ipset) not found. Please rebuild the Docker image."
    exit 1
fi

if ! command -v aggregate &> /dev/null; then
    echo "ERROR: aggregate command not found. Please rebuild the Docker image."
    exit 1
fi

iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

echo "Allowing traffic on executor port $EXECUTOR_PORT and resource port $RESOURCE_PORT"
iptables -A INPUT -p tcp --sport $EXECUTOR_PORT -j ACCEPT
iptables -A OUTPUT -p tcp --dport $EXECUTOR_PORT -j ACCEPT
iptables -A INPUT -p tcp --dport $EXECUTOR_PORT -j ACCEPT
iptables -A OUTPUT -p tcp --sport $EXECUTOR_PORT -j ACCEPT

iptables -A INPUT -p tcp --sport $RESOURCE_PORT -j ACCEPT
iptables -A OUTPUT -p tcp --dport $RESOURCE_PORT -j ACCEPT
iptables -A INPUT -p tcp --dport $RESOURCE_PORT -j ACCEPT
iptables -A OUTPUT -p tcp --sport $RESOURCE_PORT -j ACCEPT

ipset create allowed-domains hash:net

HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host IP"
    exit 1
fi

HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
echo "Host network detected as: $HOST_NETWORK"
ipset add allowed-domains "$HOST_NETWORK"

for entry in "${ALLOWED_DOMAINS[@]}"; do
    # If the argument is already an IPv4 address or CIDR range, add it directly
    if [[ "$entry" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}(/([0-9]|[12][0-9]|3[0-2]))?$ ]]; then
        echo "Adding IP/CIDR $entry"
        ipset add allowed-domains "$entry"
        continue
    fi

    echo "Resolving $entry..."
    ips=$(dig +short A "$entry")
    if [ -z "$ips" ]; then
        echo "WARNING: Failed to resolve $entry, skipping"
        continue
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "WARNING: Invalid IP from DNS for $entry: $ip, skipping"
            continue
        fi
        echo "Adding $ip for $entry"
        ipset add allowed-domains "$ip"
    done < <(echo "$ips")
done

iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT

iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

echo "Firewall initialization complete"
