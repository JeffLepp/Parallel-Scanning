import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import shlex
import time

# Map scanner number to VM IPs
VM_IPS = {
    1: "192.168.122.101",
    2: "192.168.122.102",
    3: "192.168.122.103",
    4: "192.168.122.104",
    5: "192.168.122.105",
    6: "192.168.122.106",
    7: "192.168.122.107",
    8: "192.168.122.108",
}

DEST_DIR = Path.home() / "SeedScans" / datetime.now().strftime("%Y-%m-%d")
DEST_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(qr: str) -> str:
    return qr.replace("{", "AAA").replace("}", "BBB").replace(" ", "_")

def local_filename(qr: str) -> str:
    # Keep original format, just replace spaces
    return qr.replace(" ", "_")

def run_scan(scanner_num, qr_string):
    ip = VM_IPS[scanner_num]
    
    local_safe = local_filename(qr_string)
    remote_safe = sanitize_filename(qr_string)

    local_path = DEST_DIR / f"{local_safe}.tiff"
    remote_path = f"/output/{remote_safe}.tiff"

    print(f"[scanner-{scanner_num}] Starting scan for QR: {qr_string}")

    # SSH to start scan
    try:
        subprocess.run(
            [
                "ssh", f"seedscanner@{ip}",
                f"OUTPUT_FILE='{remote_path}' python3 ~/scan.py"
            ],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[scanner-{scanner_num}] ERROR during scan: {e}")
        return

    # SCP back using the remote-safe name
    try:
        subprocess.run(
            [
                "scp",
                f"seedscanner@{ip}:{remote_path}",
                str(local_path)
            ],
            check=True
        )
        print(f"[scanner-{scanner_num}] Scan complete → {local_path}")
    except subprocess.CalledProcessError as e:
        print(f"[scanner-{scanner_num}] ERROR copying file: {e}")


def main():
    if len(sys.argv) == 1:
        print("Please paste the QR string (ensure QR codes are seperated with single-qoutes):")
        raw_qr = input("> ").strip()
    elif len(sys.argv) == 2:
        raw_qr = sys.argv[1]
    else:
        print("Usage: python3 parallelscan.py \"'QR1''QR2''QR3'\"")
        sys.exit(1)
        
    qr_codes = [qr.strip("\"'") for qr in raw_qr.split("''") if qr.strip()]

    if not qr_codes:
        print("Error: No valid QR codes found.")
        sys.exit(1)

    if len(qr_codes) > 8:
        print("Error: You can only scan up to 8 QR codes at once.")
        sys.exit(1)

    print(f"Starting parallel scan for {len(qr_codes)} scanners...")

    with ThreadPoolExecutor() as executor:
        for i, qr in enumerate(qr_codes):
            executor.submit(run_scan, i + 1, qr)
            time.sleep(1)

if __name__ == "__main__":
    main()
