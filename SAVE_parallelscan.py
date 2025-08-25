import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import shlex
import time
import os
import re

# Deadhead 
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

VM_Colors = {
    1: "Blue",
    2: "Orange",
    3: "Gray",
    4: "Green",
    5: "White",
    6: "Black",
    7: "Yellow",
    8: "Crimson"
}

DEST_DIR = Path.home() / "SeedScans" / datetime.now().strftime("%Y-%m-%d")
DEST_DIR.mkdir(parents=True, exist_ok=True)

def validate_qr_string(qr: str) -> bool:
    # Should contain only well-formed {...} chunks, no stray brackets
    return bool(re.fullmatch(r"(\{[^{}]+\})+", qr))

def sanitize_filename(qr: str) -> str:
    return qr.replace("{", "AAA").replace("}", "BBB").replace(" ", "_")

def local_filename(qr: str) -> str:
    # Keep original format, just replace spaces
    return qr.replace(" ", "_")

def run_scan(scanner_num, qr_string):
    ip = VM_IPS[scanner_num]
    
    local_safe = local_filename(qr_string)
    remote_safe = sanitize_filename(qr_string)
    
    scanner_color = VM_Colors[scanner_num]
    scanner_folder = DEST_DIR / scanner_color
    scanner_folder.mkdir(parents=True, exist_ok=True)

    local_path = DEST_DIR / scanner_folder / f"{local_safe}.tiff"
    remote_path = f"/output/{remote_safe}.tiff"

    print(f"[Scanner {scanner_color}] - Starting")

    # SSH to start scan
    try:
        subprocess.run(
            [
                "ssh", f"seedscanner@{ip}",
                f"OUTPUT_FILE='{remote_path}' python3 ~/scan.py"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
                "-q",
                f"seedscanner@{ip}:{remote_path}",
                str(local_path)
            ],
            check=True
        )
        
        expected_size = 429600000  # 429.6 MB approx
        actual_size = os.path.getsize(local_path)
        if abs(actual_size - expected_size) > 5000000:
            print(f"Scanner {scanner_color} may have corrupted")
            
        print(f"[Scanner {scanner_color}] - Complete")
        
    except subprocess.CalledProcessError as e:
        print(f"Scanner {scanner_color} had an ERROR copying file: {e}")

def run_batch(start_idx, qr_batch):
    with ThreadPoolExecutor() as executor:
        futures = {}
        for i, qr in enumerate(qr_batch):
            scanner_num = start_idx + i
            future = executor.submit(run_scan, scanner_num, qr)
            futures[future] = qr
            time.sleep(6)  # Stagger launch by 1.5 seconds per scanner
                             # A big issue with these scanners is USB bandwidth, space processing shit so nothing gets tangled/left hanging 

        for future in as_completed(futures):
            scanner_qr = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[batch-{start_idx}] Error during scan for {scanner_qr}: {e}")

def main():
    if len(sys.argv) == 1:
        print("Please paste the QR string (ensure QR codes are seperated with single-qoutes):")
        raw_qr = input("> ").strip()
    elif len(sys.argv) == 2:
        raw_qr = sys.argv[1]
    else:
        print("Usage: python3 parallelscan.py \"'QR1''QR2''QR3'\"")
        raise ValueError ("Usage: python3 parallelscan.py \"'QR1''QR2''QR3'\"")
        sys.exit(1)
        
    qr_codes = [qr.strip("\"'") for qr in raw_qr.split("''") if qr.strip()]

    if not qr_codes:
        raise ValueError("Error: No valid QR codes found.")
        print("Error: No valid QR codes found.")
        sys.exit(1)

    if len(qr_codes) > 8:
        raise ValueError("Error: You can only scan up to 8 QR codes at once.")
        print("Error: You can only scan up to 8 QR codes at once.")
        sys.exit(1)
        
    dupe_check = set()

    for idx, qr in enumerate(qr_codes, start=1):
        if qr in dupe_check:
            raise ValueError("Error: One of your QR's has been scanned twice, or is duplicated")
            sys.exit(1)
        if not validate_qr_string(qr):
            raise ValueError(f"Error: QR number {idx}'s format is incorrect (unclosed bracket or curly braces), likely the QR scanner messing up so just rescan the batch more carefully.")
        dupe_check.add(qr)


    print(f"Starting scanning jobs for {len(qr_codes)} scanners...")
    
    batch1 = qr_codes[:4]
    batch2 = qr_codes[4:]

    print("\nBatch 1 starting...\n")
    run_batch(1, batch1)

    time.sleep(3)
    if batch2:
        print("\nBatch 2 starting...\n")
        time.sleep(3)  
        run_batch(5, batch2)

    try:
        subprocess.run(["/bin/bash", "cleaner.sh"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Cleaner.sh has failed to call, please call './cleaner.sh' in the command prompt")

if __name__ == "__main__":
    main()