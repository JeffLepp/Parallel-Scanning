# Used with launch.sh


#!/usr/bin/env python3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import time
import os
import re
import fcntl

LOCK_FILE = "/tmp/seedscan_batch.lock"

# -------- VM mapping (Batch 2: scanners 5–8) --------
VM_IPS = {
    5: "192.168.122.105",
    6: "192.168.122.106",
    7: "192.168.122.107",
    8: "192.168.122.108",
}

VM_Colors = {
    5: "White",
    6: "Black",
    7: "Yellow",
    8: "Crimson",
}

# Canonical color names and mapping to scanner numbers for this batch
COLOR_CANON = {
    "WHITE":   "White",
    "BLACK":   "Black",
    "YELLOW":  "Yellow",
    "CRIMSON": "Crimson",
}

COLOR_TO_SCANNER_NUM = {
    "White":   5,  # 192.168.122.105
    "Black":   6,  # 192.168.122.106
    "Yellow":  7,  # 192.168.122.107
    "Crimson": 8,  # 192.168.122.108
}

# -------- Output directory --------
DEST_DIR = Path.home() / "SeedScans" / datetime.now().strftime("%Y-%m-%d")
DEST_DIR.mkdir(parents=True, exist_ok=True)

# -------- Helpers --------
def validate_qr_string(qr: str) -> bool:
    """QR must be one or more well-formed {...} chunks, no stray braces."""
    return bool(re.fullmatch(r"(\{[^{}]+\})+", qr))

def sanitize_filename(qr: str) -> str:
    """Make remote-safe filename (avoid braces, spaces)."""
    return qr.replace("{", "AAA").replace("}", "BBB").replace(" ", "_")

def local_filename(qr: str) -> str:
    """Keep the original content, just replace spaces."""
    return qr.replace(" ", "_")

def parse_scanned_input(raw: str):
    """
    Accept either:
      A) COLOR 'QR' COLOR 'QR' ...
         e.g., WHITE '{...}'BLACK '{...}'
      B) Legacy ''-separated QR-only
         e.g., '{...}''{...}'
    Returns (qr_codes: list[str], scanned_colors: list[str])
    """
    # Try color-tagged first for Batch 2 colors
    pairs = re.findall(r"(WHITE|BLACK|YELLOW|CRIMSON)\s*'([^']+)'", raw, flags=re.IGNORECASE)
    if pairs:
        scanned_colors = [COLOR_CANON[c.upper()] for c, _ in pairs]
        qr_codes = [q for _, q in pairs]
        return qr_codes, scanned_colors

    # Fallback: legacy QR-only input split by ''
    raise ValueError("Input must use Batch 2 colors (WHITE, BLACK, YELLOW, CRIMSON) in the form: COLOR '{QR}'. Legacy mode is disabled.")


# -------- Core scanning --------
def run_scan(scanner_num: int, qr_string: str):
    ip = VM_IPS[scanner_num]

    local_safe = local_filename(qr_string)
    remote_safe = sanitize_filename(qr_string)

    scanner_color = VM_Colors[scanner_num]
    scanner_folder = DEST_DIR / scanner_color
    scanner_folder.mkdir(parents=True, exist_ok=True)

    # NOTE: use scanner_folder (not DEST_DIR / scanner_folder)
    local_path = scanner_folder / f"{local_safe}.tiff"
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
                "scp", "-q",
                f"seedscanner@{ip}:{remote_path}",
                str(local_path)
            ],
            check=True
        )

        # Size sanity check (~429.6 MB ±5 MB)
        expected_size = 429_600_000
        actual_size = os.path.getsize(local_path)
        if abs(actual_size - expected_size) > 5_000_000:
            print(f"[Scanner {scanner_color}] Warning: file size off ({actual_size} B) — possible corruption.")

        print(f"[Scanner {scanner_color}] - Complete")

    except subprocess.CalledProcessError as e:
        print(f"[Scanner {scanner_color}] ERROR copying file: {e}")

# -------- Batch locking --------
def acquire_batch_lock(blocking_msg: str = None):
    lf = open(LOCK_FILE, "w")
    if blocking_msg:
        print(blocking_msg, flush=True)
    fcntl.flock(lf, fcntl.LOCK_EX)  # blocks until available
    return lf

def release_batch_lock(lock_fh):
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()
    except Exception:
        pass

# -------- Batch runner --------
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

# -------- Main loop --------
def main():
    while True:
        error_flag = False
        try:
            if len(sys.argv) == 1:
                print("BATCH 2: ONLY FOR SCANNERS WHITE, BLACK, YELLOW, and/or CRIMSON")
                print("Please enter color-QR entries (e.g., WHITE '{QR1}'BLACK '{QR2}'):")
                raw_qr = input("> ").strip()
            elif len(sys.argv) == 2:
                raw_qr = sys.argv[1]
            else:
                print("Usage: python3 parallelscan_batch2.py \"'QR1''QR2''QR3'\"")
                error_flag = True
                continue

            qr_codes, scanned_colors = parse_scanned_input(raw_qr)

            if scanned_colors and len(scanned_colors) != len(qr_codes):
                print("Error: Number of colors does not match number of QR codes.")
                error_flag = True
                continue

            jobs = []
            used_scanners = set()
            if scanned_colors:
                # Color-tagged mode — map each color to its scanner (5–8)
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
                # Legacy mode — sequentially map to scanners 5..8
                #jobs = [(5 + i, qr) for i, qr in enumerate(qr_codes)]
                print("Error: No color-coded entries found.")
                error_flag = True
                continue

            if not qr_codes:
                print("Error: No valid QR codes found.")
                error_flag = True
                continue

            # Limits: up to 4 per batch
            if scanned_colors and len(scanned_colors) > 4:
                print("Error: You can only scan up to 4 color-tagged items per batch.")
                error_flag = True
                continue
            if not scanned_colors and len(qr_codes) > 4:
                print("Error: You can only scan up to 4 QR codes per batch.")
                error_flag = True
                continue

            # Validate duplicates and formatting (show index on error)
            dupe_check = set()
            for idx, qr in enumerate(qr_codes, start=1):
                if qr in dupe_check:
                    print(f"Error: Duplicate QR detected at position {idx}.")
                    error_flag = True
                    continue
                if not validate_qr_string(qr):
                    print(f"Error: QR number {idx} has bad format (unclosed braces). Please rescan carefully.")
                    error_flag = True
                    continue
                dupe_check.add(qr)

            # Execute batch
            if not error_flag:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"Starting scanning jobs for {len(jobs)} scanners...")

                lock_fh = acquire_batch_lock("Another batch may be running. Waiting for available slot...")
                try:
                    print("\nBatch 2 starting...\n")
                    run_batch(jobs)

                    time.sleep(3)
                    try:
                        subprocess.run(["/bin/bash", "cleaner.sh"], check=True)
                    except subprocess.CalledProcessError:
                        print("Cleaner.sh failed — please run './cleaner.sh' manually.")
                        time.sleep(5)
                finally:
                    release_batch_lock(lock_fh)
                    os.system('cls' if os.name == 'nt' else 'clear')

        except (EOFError, KeyboardInterrupt):
            print("\nExiting batch console.")
            break

if __name__ == "__main__":
    main()
