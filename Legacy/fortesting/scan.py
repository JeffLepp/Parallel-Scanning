import subprocess
import os
import sys
import socket
from datetime import datetime

# Get VM's hostname to identify the scanner
scanner_id = socket.gethostname()

# Output filename from environment or default
output_file = os.environ.get("OUTPUT_FILE", "scan.tiff")

# Step 1: Discover connected scanner
result = subprocess.run(["scanimage", "-L"], capture_output=True, text=True)
lines = result.stdout.strip().splitlines()

scanner_name = None
for line in lines:
    if "Perfection V39" in line:
        scanner_name = line.split('`')[1].split("'")[0]
        break

if not scanner_name:
    print(f"[{scanner_id}] No scanner found.")
    print("scanimage -L output:\n", result.stdout)
    sys.exit(1)

print(f"[{scanner_id}] Found scanner: {scanner_name}")
print(f"[{scanner_id}] Saving scan to {output_file}")

# Step 2: Run the scan
try:
    with open(output_file, "wb") as f:
        result = subprocess.run([
            "scanimage",
            "-d", scanner_name,
            "--format=tiff",
            "--resolution", "1200",
            "--mode", "Color",
        ], stdout=f)

    if result.returncode == 0:
        print(f"[{scanner_id}] Scan successful → {output_file}")
    else:
        print(f"[{scanner_id}] Scan failed with code {result.returncode}")
        sys.exit(result.returncode)

except Exception as e:
    print(f"[{scanner_id}] Exception during scan: {e}")
    sys.exit(1)