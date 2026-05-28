#!/bin/bash
# Inspect Docker-related sandbox rules and only reset Docker networking when
# stale bridge-IP rules are still present.

set -euo pipefail

inspect_output="$(bash scripts/inspect_docker_networking_rules.sh)"
printf '%s\n' "$inspect_output"

stale_rules="$(
    printf '%s\n' "$inspect_output" |
        sed -nE 's/^Summary: found [0-9]+ matching rule\(s\), of which ([0-9]+) look stale\.$/\1/p' |
        tail -n 1
)"

if [[ -z "$stale_rules" ]]; then
    echo "Could not determine stale Docker networking rule count from inspector output." >&2
    exit 1
fi

if (( stale_rules > 0 )); then
    echo "Stale Docker networking rules detected; resetting Docker networking."
    bash scripts/reset_docker_networking.sh
else
    echo "No stale Docker networking rules detected; skipping reset."
fi
