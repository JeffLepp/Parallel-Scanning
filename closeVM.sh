#!/bin/bash

# List of VM names to shut down
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

echo "🛑 Shutting down all VMs..."

for vm in "${VM_NAMES[@]}"; do
  echo "🔧 Shutting down $vm..."
  virsh shutdown "$vm" >/dev/null 2>&1

  if [[ $? -eq 0 ]]; then
    echo "✅ $vm shutdown command issued."
  else
    echo "⚠️  Failed to shut down $vm (might already be off or not found)."
  fi
done

# Optional: Wait until all are off
echo "⏳ Waiting for all VMs to power off..."
for vm in "${VM_NAMES[@]}"; do
  while virsh list --name | grep -q "^$vm$"; do
    sleep 2
  done
done

echo "✅ All VMs are shut down."
