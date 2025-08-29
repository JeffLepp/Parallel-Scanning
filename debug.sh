#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# --- Config you can tweak ---
MODE="Color"
RESOLUTION="75"
SOURCE="Flatbed"
FORMAT="tiff"

# Vendor:Product for Epson V39
EPSON_VIDPID="04b8:013d"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

command -v scanimage >/dev/null || { echo "scanimage not found"; exit 1; }
command -v lsusb >/dev/null || { echo "lsusb not found"; exit 1; }

log ""
log "********************************************************************"
log "Welcome, this script will help you find out the ID's for each scanner such that we can rewire them."
log "Each scanner is named as epsonscan2:Perfection V39/GT-S650:001:XYZ:esci2:usb:ES010D:317"
log "                                           Notice the XYZ here ^^^ "
log ""
log "This XYZ will be the scanners 'ID', which will help you differentiate them. They will be real numbers (ie. 018)"
log "First we will see which scanner IDs are seen by the computer. Begin by pressing 'Enter'"
log "********************************************************************"

read -r _

log "Discovering Perfection V39 scanners ..."
# Example line:
# device `epsonscan2:Perfection V39/GT-S650:esci2:usb:ES010D:317' is a EPSON Perfection V39/GT-S650 flatbed scanner
mapfile -t V39_URIS < <(
  scanimage -L \
  | grep 'Perfection V39' \
  | cut -d'`' -f2 \
  | cut -d"'" -f1
)

if [[ ${#V39_URIS[@]} -eq 0 ]]; then
  echo "No Perfection V39 scanners found by scanimage -L." >&2
  exit 1
fi

log "Found ${#V39_URIS[@]} V39 device URI(s)."

# Pull current USB Bus:Device list for the Epson VID:PID
mapfile -t BUSDEV_LIST < <(lsusb -d "$EPSON_VIDPID" | awk '{printf "%03d:%03d\n",$2,$4+0}')

if [[ ${#BUSDEV_LIST[@]} -eq 0 ]]; then
  echo "No matching Epson V39 devices found via lsusb ($EPSON_VIDPID)." >&2
  echo "Will attempt scanning using raw URIs only."
fi

# We’ll iterate over URIs; for each, try to construct a BUS:DEV-specific string.
# If BUSDEV count is shorter, we’ll reuse the last or fall back to raw URI.
last_busdev=""
[[ ${#BUSDEV_LIST[@]} -gt 0 ]] && last_busdev="${BUSDEV_LIST[-1]}"

log ""
for uri in "${V39_URIS[@]}"; do
  id="$(cut -d: -f4 <<<"$uri")"
  log "  Scanner ID: $id   URI=$uri"
done
log ""

log "********************************************************************"
log "Above we have all our scanner IDs, if less than 8 are present then some are not being detected."
log "Please write the XYZ part of the ID on a sheet of paper, they are displayed in front of the full ID for convenience."
log ""
log "This script will launch a scan with each scanner ID."
log "You will need to write which color scanner was activated with the current ID being used."
log "This can be done by simply writing the color of the activated scanner next to the ID on your page."
log "Press 'Enter' to begin the testing, each scanner will be started automatically."
log "********************************************************************"

read -r _

idx=0
for uri in "${V39_URIS[@]}"; do
  idx=$((idx+1))
  id="$(cut -d: -f4 <<<"$uri")"

  # Split the URI into head and tail where tail begins at ':esci2:usb...'
  # head will be like: epsonscan2:Perfection V39/GT-S650
  # tail will be like: :esci2:usb:ES010D:317
  head="${uri%:esci2:*}"
  tail="${uri#${head}}"

    # Detect if head already ends with :NNN:NNN and split it out
    if [[ "$head" =~ ^(.*):([0-9]{3}):([0-9]{3})$ ]]; then
      head_base="${BASH_REMATCH[1]}"
      existing_busdev="${BASH_REMATCH[2]}:${BASH_REMATCH[3]}"
    else
      head_base="$head"
      existing_busdev=""
    fi


  # Sanity fallback if pattern didn’t match exactly
  if [[ "$tail" == "$uri" ]]; then
    # Couldn’t split; assume the entire thing after the model is the tail
    # Try to locate the first ":esci2:" occurrence
    if [[ "$uri" == *":esci2:"* ]]; then
      head="${uri%%:esci2:*}"
      tail="${uri#${head}}"
    else
      # As a last resort, treat entire uri as raw
      head="$uri"
      tail=""
    fi
  fi

  # Choose a BUS:DEV for this scanner if available
  busdev=""
  if [[ ${#BUSDEV_LIST[@]} -ge $idx ]]; then
    busdev="${BUSDEV_LIST[$((idx-1))]}"
  else
    busdev="$last_busdev"
  fi

    # If the URI already had BUS:DEV, prefer that to avoid duplication
    if [[ -n "$existing_busdev" ]]; then
    busdev="$existing_busdev"
    fi

    constructed=""
    if [[ -n "$busdev" && -n "$tail" ]]; then
    constructed="${head_base}:${busdev}${tail}"
    fi


  # Build the scan command
  # Output goes to /dev/null per your requirement
  base_cmd=(scanimage -d)
  scan_opts=(--format="$FORMAT" --mode="$MODE" --resolution "$RESOLUTION" --source "$SOURCE")

  # Try constructed BUS:DEV-specific device first (if we have one), else raw URI
  try_list=()
  if [[ -n "$constructed" ]]; then
    try_list+=("$constructed")
  fi
  try_list+=("$uri")

  success=0
  for dev in "${try_list[@]}"; do
    log "Scanning with device: $id, write the color of the active scanner next to the ID."
    if "${base_cmd[@]}" "$dev" "${scan_opts[@]}" > /dev/null \
     2> >(while IFS= read -r line; do printf '[scanimage] %s\n' "$line" >&2; done); then
      success=1
      break
    fi
  done
done

printf "\n"
log "********************************************************************"
log "All scans have been completed, if you need to double check or see again which scanners are activated with each ID, relaunch this script."
log "From here, you need to manually change the associated scanner ID's in each VM."
log "Press Enter to launch the virtual machine manager and begin associating each ID".
log "********************************************************************"

read -r _
nohup virt-manager >/dev/null 2>&1 &

log "********************************************************************"
log "You will see a menu with 8 virtual machines named after the scanner they control".
log ""
log "STEP 1: Double click scanner-1-BLUE and click on the blue information icon on the top left."
log "STEP 2: On the left, click on the menu choice labeled 'USB 04b8:013d'."
log "STEP 3: On the bottom right, click 'Remove' and confirm the removal."
log "STEP 4: On the bottom left, click on 'Add Hardware'"
log "STEP 5: On the left of the pop-up window, click 'USB Hosting Device'."
log "Step 6: From the options, click on the Perfection V39 scanner with the ID that correlated to the BLUE scanner."
log "NOTE: If a popup says this USB device is already in use just continue, you will likely change that as you go through the VM's"
log ""
log "Repeat these steps for each Virtual Machine, then power Off/On the computer."
log "********************************************************************"
