# Parallel Scanning

Demo: https://youtu.be/TUId5mshbvU

Parallel scanning tools for Epson Perfection V39 flatbed scanners. This project was designed for a specific lab setup, but the files can be reused with the right scanner, VM, and host configuration.

See `Instructions/Overview.pdf` for a system overview.

## Current Workflow

Create the host-only environment file once before launching:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set the shared scanner-VM sudo password. This file is ignored by Git.

Run the active scanner console from the repo root:

```bash
./launch.sh
```

`launch.sh` starts the VMs, opens the two active batch programs in tmux, and shuts the VMs down when the tmux session exits.

Each scanner needs to be associated with a virtual machine containing `scan.py`.

## Active Root Files

- `launch.sh` - main entrypoint.
- `SAVE_parallelscan_BATCH1.py` - scanners 1-4.
- `SAVE_parallelscan_BATCH2.py` - scanners 5-8.
- `cleaner.sh` - cleans remote VM outputs after scanning.
- `startVM.sh` / `closeVM.sh` - VM lifecycle helpers.
- `debug.sh` - scanner ID/debug helper.
- `scan.py` - script installed/run on each scanner VM.

Older scan variants live under `Legacy/`.

## Instructions

The `Instructions/` folder contains PDFs for setup and operator use:

- `Scanning Instructions.pdf` is designed for QR scanning so undergraduate students with no coding experience can use the system in the lab.
- `Parallel Epson V39 Scanner System.pdf` gives a general overview of the system and its dependencies, including virtual machine and scanner setup.

## Dependencies

In each virtual machine:

- `sane`
- `sane-utils`
- `usbutils`
- `python3`
- `usbreset`

On the host machine:

- `qemu-kvm`
- `virt-manager`
- `tmux`
- `python3`
- `usbutils`
