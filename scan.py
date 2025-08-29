#Script that is inserted into each VM controlling each Scanner (Needs to be encapsulated to allow multiple active instances)

import subprocess
import os
import sys
import socket
from datetime import datetime
import time

subprocess.run(["pkill", "-f", "scanimage"])

time.sleep(1)

def find_scanner_dev_path(vendor="04b8", product="013d"):
    lsusb_output = subprocess.run(["lsusb"], capture_output=True, text=True).stdout.strip().splitlines()
    for line in lsusb_output:
        if f"{vendor}:{product}" in line:
            parts = line.split()
            bus = parts[1]
            device = parts[3].strip(":")
            return f"/dev/bus/usb/{bus}/{device}"
    return None

# Get VM's hostname to identify the scanner
scanner_id = socket.gethostname()

# Output filename from environment or default
output_file = os.environ.get("OUTPUT_FILE", "scan.tiff")

# Step 1: Discover connected scanner
result = subprocess.run(["scanimage", "-L"], capture_output=True, text=True)
lines = result.stdout.strip().splitlines()

scanner_name = None
for line in lines:
    if "Perfection V39" in line and ":usb:" in line and line.startswith("device `"):
        scanner_name = line.split("`")[1].split("'")[0]  # Correctly extract the device string
        break

if not scanner_name:
    print(f"[{scanner_id}] No scanner found.")
    print("scanimage -L output:\n", result.stdout)
    sys.exit(1)

#print(f"[{scanner_id}] Found scanner: {scanner_name}")
#print(f"[{scanner_id}] Saving scan to {output_file}")

dev_path = find_scanner_dev_path()
if dev_path:
    subprocess.run(["sudo", "usbreset", dev_path])
    time.sleep(1)
else:
    print(f"[{scanner_id}] Warning: couldn't find dev_path for usbreset (continuing anyway)")

# Step 2: Run the scan
try:
    time.sleep(1)
    with open(output_file, "wb") as f:
        result = subprocess.run([
            "scanimage",
            "-d", scanner_name,
            "--format=tiff",
            "--resolution", "1200",
            "--mode", "Color",
            "--source", "Flatbed"
        ], stdout=f, check=True)


    if result.returncode != 0:
        print(f"[{scanner_id}] Scan failed with code {result.returncode}")
        sys.exit(result.returncode)
        
except subprocess.CalledProcessError as e:
    print(f"[{scanner_id}] Scan failed: {e}")
    sys.exit(e.returncode)

except Exception as e:
    print(f"[{scanner_id}] Exception during scan: {e}")
    sys.exit(1)