#!/usr/bin/env python3
# Arch Linux ZFS Installer
# Main entry point for the installer

import os
import sys
import argparse
from InquirerPy import inquirer

from utils.disk_manager import DiskManager
from utils.zfs_manager import ZFSManager
from utils.system_config import SystemConfig
from utils.boot_manager import BootManager
from utils.installer import Installer

def main():
    print("=" * 80)
    print("Arch Linux ZFS Installer")
    print("=" * 80)
    print("\nWARNING: This installer will modify your system. Make sure you have")
    print("a backup of all important data before proceeding.\n")
    
    # Check for root privileges
    if os.geteuid() != 0:
        print("Error: This installer must be run with root privileges.")
        print("Please run this script with sudo or as the root user.")
        sys.exit(1)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Arch Linux ZFS Installer")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    
    # Initialize components
    disk_manager = DiskManager()
    zfs_manager = ZFSManager()
    boot_manager = BootManager()
    system_config = SystemConfig()
    installer = Installer(disk_manager, zfs_manager, boot_manager, system_config)
    
    # Start installation workflow
    try:
        # 1. Disk selection and partitioning
        disk_manager.select_disk()
        disk_manager.create_partitions()
        
        # 2. ZFS pool and dataset setup
        zfs_manager.setup_pool()
        zfs_manager.create_pool(disk_manager.partitions['zfs'])
        zfs_manager.create_datasets()
        
        # 3. Boot configuration
        boot_manager.setup_boot_partitions()
        
        # 4. Mount filesystems
        installer.mount_filesystems()
        
        # 5. System installation
        installer.install_base_system()
        
        # 6. System configuration
        system_config.configure_system()
        
        # 7. Bootloader installation
        boot_manager.install_bootloader()
        
        # 8. Finalization
        installer.finalize_installation()
        
        print("\nInstallation completed successfully!")
        print("You can now reboot into your new Arch Linux system.")
        print("Don't forget to export the ZFS pool before rebooting:")
        print("  # zpool export rpool")
        
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError during installation: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 