#!/bin/bash

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

# Hardcoded sudo password
SSHPASS="Seeds!"
THRESHOLD_GB=1

echo ""
echo "Starting cleanup on all VMs..."

for ip in "${VM_IPS[@]}"; do
  #echo "Cleaning $ip..."

  ssh seedscanner@$ip "echo '$SSHPASS' | sudo -S rm -f /output/*.tiff && \
                       echo '$SSHPASS' | sudo -S journalctl --vacuum-time=5s && \
                       echo '$SSHPASS' | sudo -S apt clean && \
                       df -h / >/dev/null 2>&1" >/dev/null 2>&1

  avail_gb=$(ssh -q seedscanner@$ip "df -BG / | awk 'NR==2 {print \$4}' | sed 's/G//'")
  if [[ $avail_gb -lt $THRESHOLD_GB ]]; then
    echo "WARNING: $ip has low free space on / (${avail_gb}G available)"
  fi

done

echo "All VMs cleaned."
