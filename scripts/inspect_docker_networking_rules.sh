#!/bin/bash
# Inspect sandbox-style iptables rules left by CLI-agent / DockerSandkasten runs.
# The script is read-only: it reports matching rules in INPUT and DOCKER-USER,
# and labels each source IP as live or stale relative to the Docker bridge
# network.

set -euo pipefail

BRIDGE_NETWORK="bridge"
CHAINS=("INPUT" "DOCKER-USER")
matched_rules=0
stale_rules=0

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required but not installed." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but not installed." >&2
    exit 1
fi

bridge_subnet="$(docker network inspect "$BRIDGE_NETWORK" --format '{{(index .IPAM.Config 0).Subnet}}')"
if [[ -z "$bridge_subnet" || "$bridge_subnet" == "<no value>" ]]; then
    echo "Could not determine the subnet for Docker network '$BRIDGE_NETWORK'." >&2
    exit 1
fi

declare -A live_bridge_ips=()
while IFS= read -r raw_ip; do
    raw_ip="${raw_ip%%/*}"
    if [[ -n "$raw_ip" ]]; then
        live_bridge_ips["$raw_ip"]=1
    fi
done < <(docker network inspect "$BRIDGE_NETWORK" --format '{{range .Containers}}{{println .IPv4Address}}{{end}}')

ip_in_bridge_subnet() {
    local ip="$1"
    python3 - "$ip" "$bridge_subnet" <<'PY'
import ipaddress
import sys

ip = ipaddress.ip_address(sys.argv[1])
network = ipaddress.ip_network(sys.argv[2], strict=False)
sys.exit(0 if ip in network else 1)
PY
}

extract_source_ip() {
    local line="$1"
    local source

    source="$(sed -nE 's/.*-s[[:space:]]+([^[:space:]]+).*/\1/p' <<<"$line")"
    source="${source%%/*}"
    printf '%s\n' "$source"
}

is_sandbox_rule() {
    local chain="$1"
    local line="$2"

    case "$chain" in
        "DOCKER-USER")
            [[ "$line" =~ ^-A[[:space:]]DOCKER-USER[[:space:]]-s[[:space:]][^[:space:]]+[[:space:]]-j[[:space:]]DROP$ ]]
            ;;
        "INPUT")
            [[ "$line" =~ ^-A[[:space:]]INPUT[[:space:]]-s[[:space:]][^[:space:]]+[[:space:]]-j[[:space:]]DROP$ ]] || \
            [[ "$line" =~ ^-A[[:space:]]INPUT[[:space:]]-s[[:space:]][^[:space:]]+[[:space:]]-p[[:space:]]tcp([[:space:]]-m[[:space:]]tcp)?[[:space:]]--dport[[:space:]][0-9]+[[:space:]]-j[[:space:]]ACCEPT$ ]]
            ;;
        *)
            return 1
            ;;
    esac
}

echo "Docker bridge subnet: $bridge_subnet"
if ((${#live_bridge_ips[@]} > 0)); then
    echo "Live bridge container IPs:"
    for ip in "${!live_bridge_ips[@]}"; do
        echo "  $ip"
    done
else
    echo "No live containers are currently attached to the bridge network."
fi

for chain in "${CHAINS[@]}"; do
    echo
    echo "Inspecting $chain..."
    if ! rules_output="$(sudo iptables -S "$chain" 2>/dev/null)"; then
        echo "Skipping missing iptables chain: $chain"
        continue
    fi

    chain_matches=0
    while IFS= read -r line; do
        [[ "$line" == -A* ]] || continue
        is_sandbox_rule "$chain" "$line" || continue

        source_ip="$(extract_source_ip "$line")"
        [[ -n "$source_ip" ]] || continue

        if ! ip_in_bridge_subnet "$source_ip"; then
            continue
        fi

        status="stale"
        if [[ -n "${live_bridge_ips[$source_ip]:-}" ]]; then
            status="live"
        else
            stale_rules=$((stale_rules + 1))
        fi

        echo "[$status] $line"
        matched_rules=$((matched_rules + 1))
        chain_matches=$((chain_matches + 1))
    done <<<"$rules_output"

    if ((chain_matches == 0)); then
        echo "No matching sandbox-style rules found in $chain."
    fi
done

echo
echo "Summary: found $matched_rules matching rule(s), of which $stale_rules look stale."
