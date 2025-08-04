#!/bin/bash

# List of VM names to start
VM_NAMES=(
  scanner-1
  scanner-2
  scanner-3
  scanner-4
  scanner-5
  scanner-6
  scanner-7
  scanner-8
)

echo "🚀 Starting all VMs..."

for vm in "${VM_NAMES[@]}"; do
  echo "🔧 Starting $vm..."
  virsh start "$vm" >/dev/null 2>&1

  if [[ $? -eq 0 ]]; then
    echo "✅ $vm started."
  else
    echo "⚠️  Failed to start $vm (might already be running)."
  fi
done

echo "✅ All VMs processed."