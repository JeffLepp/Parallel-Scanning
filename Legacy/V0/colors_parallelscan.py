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

# Invert to COLOR -> scanner_num (uppercased for case-insensitive match)
COLOR_TO_NUM = {v.upper(): k for k, v in VM_Colors.items()}

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

    # Fix: avoid DEST_DIR duplication
    local_path = scanner_folder / f"{local_safe}.tiff"
    remote_path = f"/output/{remote_safe}.tiff"

    print(f"[Scanner {scanner_color}] - Starting")
    # SSH to start scan
    try:
        subprocess.run(
            [
                "ssh",
                f"seedscanner@{ip}",
                # keep minimal change: set env var then run script
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

def run_batch(scanner_nums, qr_batch):
    """
    Minimal change: instead of start_idx + i, we pass explicit scanner numbers
    aligned with qr_batch positions.
    """
    with ThreadPoolExecutor() as executor:
        futures = {}
        for i, qr in enumerate(qr_batch):
            scanner_num = scanner_nums[i]
            future = executor.submit(run_scan, scanner_num, qr)
            futures[future] = qr
            time.sleep(6)  # Stagger launch
        # A big issue with these scanners is USB bandwidth, space processing
        # shit so nothing gets tangled/left hanging
        for future in as_completed(futures):
            scanner_qr = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[batch] Error during scan for {scanner_qr}: {e}")

def chunk4(seq):
    """Yield successive chunks of size 4."""
    for i in range(0, len(seq), 4):
        yield seq[i:i+4]

def parse_color_qr_pairs(text):
    """
    Parse repeated pairs like:
    BLUE '...QR1...'ORANGE '...QR2...'GRAY '...QR3...'
    Spaces between pairs are optional.
    Color is a-z letters; QR is anything inside single quotes (no embedded single quotes).
    Returns: (scanner_nums[], qr_codes[])
    """
    pairs = re.findall(r"([A-Za-z]+)\s*'([^']+)'", text)
    if not pairs:
        return [], []

    scanner_nums = []
    qr_codes = []
    for color_raw, qr in pairs:
        color = color_raw.upper()
        if color not in COLOR_TO_NUM:
            raise ValueError(f"Unknown color '{color_raw}'. Valid: {', '.join(sorted(COLOR_TO_NUM.keys()))}")
        scanner_num = COLOR_TO_NUM[color]
        scanner_nums.append(scanner_num)
        qr_codes.append(qr.strip())
    return scanner_nums, qr_codes

def main():
    # Input now expects repeated COLOR 'QR' pairs, e.g.:
    # BLUE '{...}'ORANGE '{...}'GRAY '{...}'
    if len(sys.argv) == 1:
        print("Paste COLOR 'QR' pairs (e.g., BLUE '{...}'ORANGE '{...}'):")
        raw = input("> ").strip()
    elif len(sys.argv) == 2:
        raw = sys.argv[1]
    else:
        print("Usage: python3 parallelscan.py \"BLUE '{...}'ORANGE '{...}'GRAY '{...}'\"")
        raise ValueError("Usage: python3 parallelscan.py \"BLUE '{...}'ORANGE '{...}'GRAY '{...}'\"")

    scanner_nums, qr_codes = parse_color_qr_pairs(raw)

    if not qr_codes:
        raise ValueError("Error: No valid COLOR 'QR' pairs found.")

    if len(qr_codes) > 8:
        raise ValueError("Error: You can only scan up to 8 QR codes at once.")

    # Ensure no duplicate scanners (colors) are specified
    if len(set(scanner_nums)) != len(scanner_nums):
        raise ValueError("Error: You assigned the same color/scanner more than once in this batch.")

    # Validate QRs and duplicates
    dupe_check = set()
    for idx, qr in enumerate(qr_codes, start=1):
        if qr in dupe_check:
            raise ValueError(f"Error: QR number {idx} is duplicated in your input.")
        if not validate_qr_string(qr):
            raise ValueError(f"Error: QR number {idx}'s format is incorrect (unclosed bracket/brace). Rescan the batch carefully.")
        dupe_check.add(qr)

    print(f"Starting scanning jobs for {len(qr_codes)} scanners...")

    # Preserve your two-batch behavior: first up to 4, then the rest
    # We must keep scanner_nums aligned with qr_codes, so chunk both in lockstep.
    pairs = list(zip(scanner_nums, qr_codes))
    chunks = list(chunk4(pairs))

    for i, chunk in enumerate(chunks, start=1):
        colors_in_batch = [VM_Colors[num] for num, _ in chunk]
        print(f"\nBatch {i} starting with: {', '.join(colors_in_batch)}\n")
        batch_scanners = [num for num, _ in chunk]
        batch_qrs = [qr for _, qr in chunk]
        # small pause between batches to mirror your old flow
        if i > 1:
            time.sleep(3)
        run_batch(batch_scanners, batch_qrs)

    # Run cleaner if present
    try:
        subprocess.run(["/bin/bash", "cleaner.sh"], check=True)
    except subprocess.CalledProcessError:
        print("Cleaner.sh failed. Please run './cleaner.sh' manually.")

if __name__ == "__main__":
    main()
