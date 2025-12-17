#!/bin/bash

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

SSHPASS="Seeds!"

echo "🚀 Starting cleanup + qcow2 compaction..."

for vm in "${VM_NAMES[@]}"; do
  echo "🔧 Cleaning inside $vm..."

  # Get last octet from scanner-X
  num=$(echo "$vm" | grep -oE '[0-9]+')
  ip="192.168.122.10$num"

  ssh seedscanner@$ip "echo '$SSHPASS' | sudo -S rm -f /output/*.tiff && \
                       echo '$SSHPASS' | sudo -S journalctl --vacuum-time=5s && \
                       echo '$SSHPASS' | sudo -S apt clean && \
                       echo '$SSHPASS' | sudo -S dd if=/dev/zero of=/zerofile bs=1M status=none || true && \
                       echo '$SSHPASS' | sudo -S rm -f /zerofile && \
                       df -h /"

  echo "🛑 Shutting down $vm..."
  virsh shutdown "$vm"
done

echo "⏳ Waiting for shutdown..."
for vm in "${VM_NAMES[@]}"; do
  while virsh list --name --state-running | grep -q "$vm"; do
    sleep 2
  done
done

echo "🧊 Compacting qcow2 disks..."

for vm in "${VM_NAMES[@]}"; do
  disk_path=$(virsh domblklist "$vm" | awk '/\.qcow2/ {print $2}')
  if [[ ! -f "$disk_path" ]]; then
    echo "❌ Could not find disk for $vm, skipping."
    continue
  fi

  compacted_path="${disk_path%.qcow2}-compacted.qcow2"

  echo "➤ Compacting $disk_path..."
  qemu-img convert -O qcow2 -c "$disk_path" "$compacted_path"

  echo "🔁 Swapping in compacted image..."
  mv "$disk_path" "${disk_path%.qcow2}-old.qcow2"
  mv "$compacted_path" "$disk_path"
done

echo "✅ All VMs cleaned and disk images compacted."
echo "🛑 VMs are still powered off. Please restart the host before scanning again to restore USB connections."
