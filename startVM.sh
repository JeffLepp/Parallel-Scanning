#!/bin/bash
error_flag=0

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

echo "Starting all VMs, please hold..."
echo ""

for vm in "${VM_NAMES[@]}"; do
  echo "Starting $vm..."
  virsh start "$vm" >/dev/null 2>&1

  if [[ $? -eq 0 ]]; then
    echo "   $vm started."
  else
    echo "Failed to start $vm (might already be running)."
    error_flag=1
  fi
done

if [[ $error_flag -eq 1 ]]; then
  echo ""
  echo "One or more scanners failed to launch, It would be best to follow the debugging instructions."
  echo "If you decide to do so, close out of the terminal before shutting down."
  echo "Press 'Enter' to continue to program."

  read -r _

fi

echo "All VMs processed."