# Used with launch.sh

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import shlex
import time
import os
import re
import fcntl
LOCK_FILE = "/tmp/seedscan_batch.lock"


# Deadhead 
# Map scanner number to VM IPs
VM_IPS = {
    1: "192.168.122.101",
    2: "192.168.122.102",
    3: "192.168.122.103",
    4: "192.168.122.104"
}

VM_Colors = {
    1: "Blue",
    2: "Orange",
    3: "Gray",
    4: "Green"
}

COLOR_CANON = {
    "BLUE":   "Blue",
    "ORANGE": "Orange",
    "GRAY":   "Gray",
    "GREEN":  "Green",
}

COLOR_TO_SCANNER_NUM = {
    "Blue": 1,   # 192.168.122.101
    "Orange": 2, # 192.168.122.102
    "Gray": 3,   # 192.168.122.103
    "Green": 4,  # 192.168.122.104
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

def parse_scanned_input(raw: str):
    """
    Accepts either:
      A) COLOR 'QR' COLOR 'QR' ...
         e.g., BLUE '{...}'ORANGE '{...}'
      B) Legacy ''-separated QR-only
         e.g., '{...}''{...}'
    Returns (qr_codes: list[str], scanned_colors: list[str])
    """
    # Try color-tagged first
    pairs = re.findall(r"(BLUE|ORANGE|GRAY|GREEN)\s*'([^']+)'", raw, flags=re.IGNORECASE)
    if pairs:
        scanned_colors = [COLOR_CANON[c.upper()] for c, _ in pairs]
        qr_codes = [q for _, q in pairs]
        return qr_codes, scanned_colors

    # Fallback: legacy QR-only input split by ''
    qr_codes = [qr.strip("\"'") for qr in raw.split("''") if qr.strip()]
    scanned_colors = []
    return qr_codes, scanned_colors

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
        
def acquire_batch_lock(blocking_msg: str = None):
    lf = open(LOCK_FILE, "w")
    if blocking_msg:
        print(blocking_msg, flush=True)
    # This will BLOCK until the other batch releases the lock
    fcntl.flock(lf, fcntl.LOCK_EX)
    return lf

def release_batch_lock(lock_fh):
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()
    except Exception:
        pass


def run_batch(jobs):
    """
    jobs: list[tuple[int, str]] like [(scanner_num, qr_string), ...]
    """
    with ThreadPoolExecutor() as executor:
        futures = {}
        for scanner_num, qr in jobs:
            future = executor.submit(run_scan, scanner_num, qr)
            futures[future] = (scanner_num, qr)
            time.sleep(6)  # stagger to reduce USB/CPU contention

        for future in as_completed(futures):
            scanner_num, scanner_qr = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[scanner-{scanner_num}] Error during scan for {scanner_qr}: {e}")

def main():
    while True:
        error_flag = False
        try:
            if len(sys.argv) == 1:
                print("BATCH 1: ONLY FOR SCANNERS BLUE, ORANGE, GRAY, and/or GREEN")
                print("Please enter color-QR entries (e.g., BLUE '{QR1}'ORANGE '{QR2}')")
                raw_qr = input("> ").strip()
            elif len(sys.argv) == 2:
                raw_qr = sys.argv[1]
            else:
                print("Usage: python3 parallelscan.py \"'QR1''QR2''QR3'\"")
                error_flag = True
                continue
                
            qr_codes, scanned_colors = parse_scanned_input(raw_qr)
            
            if scanned_colors and len(scanned_colors) != len(qr_codes):
                print("Error: Number of colors does not match number of QR codes.")
                error_flag = True
                continue
            
            jobs = []
            used_scanners = set()
            if scanned_colors:  # color-tagged mode
                for color, qr in zip(scanned_colors, qr_codes):
                    scanner_num = COLOR_TO_SCANNER_NUM.get(color)
                    if scanner_num is None:
                        print(f"Error: Unknown color '{color}'.")
                        error_flag = True
                        break
                    if scanner_num in used_scanners:
                        print(f"Error: Color '{color}' (scanner {scanner_num}) used twice in one batch.")
                        error_flag = True
                        break
                    jobs.append((scanner_num, qr))
                    used_scanners.add(scanner_num)
            else:
                # legacy mode: map sequentially 1..N
                jobs = [(i + 1, qr) for i, qr in enumerate(qr_codes)]

            if not qr_codes:
                print("Error: No valid QR codes found.")
                error_flag = True
                continue

            if len(scanned_colors) > 0 and len(scanned_colors) > 4:
                print("Error: You can only scan up to 4 color-tagged items per batch.")
                error_flag = True
                continue
            if len(scanned_colors) == 0 and len(qr_codes) > 4:
                print("Error: You can only scan up to 4 QR codes per batch.")
                error_flag = True
                continue
                
            dupe_check = set()

            for idx, qr in enumerate(qr_codes, start=1):
                if qr in dupe_check:
                    print("Error: One of your QR's has been scanned twice, or is duplicated")
                    error_flag = True
                    continue
                if not validate_qr_string(qr):
                    print(f"Error: QR number {idx}'s format is incorrect (unclosed bracket or curly braces), likely the QR scanner messing up so just rescan the batch more carefully.")
                    error_flag = True
                    continue
                
                dupe_check.add(qr)

            if error_flag == False:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"Starting scanning jobs for {len(jobs)} scanners...")

                lock_fh = acquire_batch_lock("Another batch may be running. Waiting for available slot...")
                try:
                    print("\nBatch 1 starting...\n")
                    run_batch(jobs)  # <-- use jobs, not (1, batch2)

                    time.sleep(3)
                    try:
                        subprocess.run(["/bin/bash", "cleaner.sh"], check=True)
                    except subprocess.CalledProcessError:
                        print("Cleaner.sh has failed to call, please run './cleaner.sh' manually.")
                        time.sleep(5)
                finally:
                    release_batch_lock(lock_fh)
                    os.system('cls' if os.name == 'nt' else 'clear')
                                            
        except (EOFError, KeyboardInterrupt):
            print("\nExiting batch console.")
            break
        
if __name__ == "__main__":
    main()