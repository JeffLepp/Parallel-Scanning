#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SEEDSCAN_ENV_FILE:-$SCRIPT_DIR/.env}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "ERROR: Missing $ENV_FILE." >&2
  echo "Copy .env.example to .env and set SEEDSCAN_SUDO_PASSWORD." >&2
  exit 1
fi

# This is a trusted, user-owned Bash configuration file.
# shellcheck disable=SC1090
source "$ENV_FILE"
: "${SEEDSCAN_SUDO_PASSWORD:?SEEDSCAN_SUDO_PASSWORD is not configured in $ENV_FILE}"

# IPs of all VMs to clean
VM_IPS=(
  192.168.122.101
  192.168.122.102
  192.168.122.103
  192.168.122.104
  192.168.122.105
  192.168.122.106
  192.168.122.107
  192.168.122.108
)

THRESHOLD_GB=1
SSH_OPTIONS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
)
cleanup_failed=0

echo ""
echo "Starting cleanup on all VMs..."

for ip in "${VM_IPS[@]}"; do
  if ! printf '%s\n' "$SEEDSCAN_SUDO_PASSWORD" \
    | ssh "${SSH_OPTIONS[@]}" "seedscanner@$ip" \
        "sudo -S -p '' /bin/sh -c 'rm -f /output/*.tiff && journalctl --vacuum-time=5s && apt-get clean'" \
        >/dev/null 2>&1; then
    echo "WARNING: Cleanup failed on $ip." >&2
    cleanup_failed=1
    continue
  fi

  if ! avail_gb=$(ssh -q "${SSH_OPTIONS[@]}" "seedscanner@$ip" \
      "df -BG / | awk 'NR==2 {print \$4}' | sed 's/G//'" 2>/dev/null); then
    echo "WARNING: Could not check free space on $ip." >&2
    cleanup_failed=1
    continue
  fi

  if [[ ! "$avail_gb" =~ ^[0-9]+$ ]]; then
    echo "WARNING: Invalid free-space response from $ip." >&2
    cleanup_failed=1
  elif (( avail_gb < THRESHOLD_GB )); then
    echo "WARNING: $ip has low free space on / (${avail_gb}G available)"
  fi
done

unset SEEDSCAN_SUDO_PASSWORD

if (( cleanup_failed )); then
  echo "Cleanup completed with one or more warnings." >&2
  exit 1
fi

echo "All VMs cleaned successfully."
