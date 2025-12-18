Demo: https://youtu.be/M6JMAnmT8rg

# Parallel-Scanning
Enables parrellel scanning of Epson scanners, designed for Perfection V39 flatbed scanners. While it was designed for the purposes of a specific lab, these files can be used by you too given proper setup. It was made to be reliable and easy to use once configured, but this was done soley by me during my free time from the lab - so it's not perfect or a final product.

Each scanner needs to be associated with a Virtual Machine containing Scan.py (Replace ID within it to match Epson Scanner ID)
launch.sh will gather virtual machines and allow for running.

Each terminal side corresponds to a set of 4 scanners, input as many as 4 names as directed to launch all 4 scanners.

# Files actively used are in the main directory
launch.sh - what you will call to launch your system

startVM.sh - shell script to automatically handle VM launching in virt-manager

closeVM.sh - shell script to automatically close and clean out VM's for state preservation 

debug.sh - shell script to aid in associating each VM and USB scanner address

SAVE_parallelscan_BATCH1.py

SAVE_parallelscan_BATCH2.py

scan.py (inside each VM)

# Legacy or archival files if interested in previous versions:
parallelscan_BATCH1.py

parallelscan_BATCH2.py

launch_legacy.sh

SAVE_parallelscan.py

colors_parallelscan.py

Journal.txt

# Instructions in Instructions folder
Scanning Instructions.pdf is designed for QR scanning so undergraduate students with no coding experience can use the system at the lab easily - I would suggest making a similar PDF if you successfully implement a similar system to this. 

Parallel Epson V39 Scanner System.pdf is designed to be a general overview of the system and it's dependencies. It provides details on implementing the virtual machines and scanner setup. 

# Dependencies
In Each Virtual Machine:
  sane 
  sane-utils 
  usbutils 
  python3 
  usbreset

On Host Machine (Physical Computer):
  qemu-kvm 
  virt-manager 
  tmux 
  python3 
  usbutils
