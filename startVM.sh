#!/bin/bash

# List of VM names to start
VM_NAMES=(
  scanner-1-BLUE
  scanner-2-ORANGE
  scanner-3-GRAY
  scanner-4-GREEN
  scanner-5-WHITE
  scanner-6-BLACK
  scanner-7-YELLOW
  scanner-8-CRIMSON
)

echo "Starting all VMs..."

for vm in "${VM_NAMES[@]}"; do
  echo "Starting $vm..."
  virsh start "$vm" >/dev/null 2>&1

  if [[ $? -eq 0 ]]; then
    echo "$vm started."
  else
    echo "Failed to start $vm (might already be running)."
  fi
done

echo "All VMs processed."