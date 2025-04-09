#!/usr/bin/env python3
# Disk Manager Module
# Handles disk operations, partitioning, and disk information display

import os
import subprocess
import json
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

class DiskManager:
    def __init__(self):
        self.selected_disk = None
        self.partitions = {
            'efi': None,
            'boot': None,
            'zfs': None
        }
        self.partition_scheme = "full"  # Options: full, manual, existing
        self.use_separate_boot = False
    
    def get_available_disks(self):
        """Get a list of available disks using lsblk"""
        try:
            cmd = ["lsblk", "-pdo", "NAME,SIZE,MODEL", "-e", "7,11"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            disks = []
            for line in result.stdout.splitlines()[1:]:  # Skip header line
                parts = line.strip().split(maxsplit=2)
                if len(parts) >= 2:
                    disk_path = parts[0]
                    disk_size = parts[1]
                    disk_model = parts[2] if len(parts) > 2 else ""
                    disks.append({
                        'path': disk_path,
                        'size': disk_size,
                        'model': disk_model
                    })
            return disks
        except subprocess.CalledProcessError as e:
            print(f"Error getting disk list: {e}")
            return []
    
    def get_disk_info(self, disk_path):
        """Get detailed information about a specific disk"""
        try:
            # Get partition information
            cmd = ["lsblk", "-pJo", "NAME,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL", disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            disk_info = json.loads(result.stdout)
            
            # Get partition table type
            cmd = ["parted", "-s", disk_path, "print"]
            part_info = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                'partitions': disk_info.get('blockdevices', [{}])[0].get('children', []),
                'part_info': part_info.stdout
            }
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"Error getting disk info: {e}")
            return {'partitions': [], 'part_info': ''}
    
    def select_disk(self):
        """Interactive disk selection"""
        disks = self.get_available_disks()
        
        if not disks:
            raise Exception("No disks found. Cannot continue.")
        
        choices = []
        for disk in disks:
            label = f"{disk['path']} ({disk['size']}) - {disk['model']}"
            choices.append(Choice(value=disk['path'], name=label))
        
        self.selected_disk = inquirer.select(
            message="Select a disk to install Arch Linux with ZFS:",
            choices=choices,
        ).execute()
        
        # After selecting disk, choose partition scheme
        self.select_partition_scheme()
        
        return self.selected_disk
    
    def select_partition_scheme(self):
        """Choose how to partition the selected disk"""
        print(f"\nDisk {self.selected_disk} selected.")
        
        # Display current partitions
        disk_info = self.get_disk_info(self.selected_disk)
        if disk_info['partitions']:
            print("\nCurrent partitions:")
            for part in disk_info['partitions']:
                print(f"  {part['name']} ({part['size']}) - {part.get('fstype', 'unknown')}")
        
        # Ask for partitioning scheme
        scheme = inquirer.select(
            message="Choose partitioning method:",
            choices=[
                Choice("full", "Use entire disk (will erase ALL data)"),
                Choice("manual", "Manual partitioning"),
                Choice("existing", "Use existing partitions")
            ]
        ).execute()
        
        self.partition_scheme = scheme
        
        # Ask if separate /boot partition is needed
        self.use_separate_boot = inquirer.confirm(
            message="Do you want to create a separate /boot partition? (Recommended for GRUB)"
        ).execute()
        
        return self.partition_scheme
    
    def create_partitions(self):
        """Create partitions based on the selected scheme"""
        if self.partition_scheme == "full":
            self._create_full_disk_partitions()
        elif self.partition_scheme == "manual":
            self._create_manual_partitions()
        elif self.partition_scheme == "existing":
            self._select_existing_partitions()
        
        print("\nPartition setup completed.")
        return self.partitions
    
    def _create_full_disk_partitions(self):
        """Create a standard partition layout using the entire disk"""
        print(f"\nCreating partitions on {self.selected_disk}...")
        
        # Confirm before wiping the disk
        confirm = inquirer.confirm(
            message=f"WARNING: This will erase ALL data on {self.selected_disk}. Continue?",
            default=False
        ).execute()
        
        if not confirm:
            raise Exception("Partitioning cancelled by user.")
        
        try:
            # Create a new GPT partition table
            subprocess.run(["sgdisk", "--zap-all", self.selected_disk], check=True)
            
            # Create EFI System Partition (512 MiB)
            efi_partition = subprocess.run(
                ["sgdisk", "--new=1:0:+512M", "--typecode=1:ef00", "--change-name=1:EFI", self.selected_disk],
                capture_output=True, text=True, check=True
            )
            
            if self.use_separate_boot:
                # Create a separate boot partition (1 GiB)
                boot_partition = subprocess.run(
                    ["sgdisk", "--new=2:0:+1G", "--typecode=2:8300", "--change-name=2:BOOT", self.selected_disk],
                    capture_output=True, text=True, check=True
                )
                # Create ZFS partition (rest of disk)
                zfs_partition = subprocess.run(
                    ["sgdisk", "--new=3:0:0", "--typecode=3:bf00", "--change-name=3:ZFS", self.selected_disk],
                    capture_output=True, text=True, check=True
                )
                
                # Store partition information
                self.partitions['efi'] = f"{self.selected_disk}1"
                self.partitions['boot'] = f"{self.selected_disk}2"
                self.partitions['zfs'] = f"{self.selected_disk}3"
            else:
                # Create ZFS partition (rest of disk)
                zfs_partition = subprocess.run(
                    ["sgdisk", "--new=2:0:0", "--typecode=2:bf00", "--change-name=2:ZFS", self.selected_disk],
                    capture_output=True, text=True, check=True
                )
                
                # Store partition information
                self.partitions['efi'] = f"{self.selected_disk}1"
                self.partitions['zfs'] = f"{self.selected_disk}2"
            
            # Inform the kernel about the new partitions
            subprocess.run(["partprobe", self.selected_disk], check=True)
            
            # Format EFI partition
            subprocess.run(["mkfs.fat", "-F32", self.partitions['efi']], check=True)
            
            # Format boot partition if it exists
            if self.use_separate_boot:
                subprocess.run(["mkfs.ext4", self.partitions['boot']], check=True)
            
            print("Partitions created and formatted successfully.")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error during partitioning: {e}")
    
    def _create_manual_partitions(self):
        """Allow user to manually create partitions"""
        print("\nManual partitioning selected.")
        print("Please create the following partitions:")
        print("1. EFI System Partition (at least 512 MiB, type EF00)")
        print("2. Optional Boot partition (at least 1 GiB, type 8300)")
        print("3. ZFS partition (remaining space, type BF00)")
        
        print("\nUse a partitioning tool like 'fdisk' or 'parted' to create these partitions.")
        print("Example: sgdisk --zap-all /dev/sdX  # Warning: erases all data")
        print("         sgdisk --new=1:0:+512M --typecode=1:ef00 /dev/sdX  # EFI partition")
        print("         sgdisk --new=2:0:+1G --typecode=2:8300 /dev/sdX    # Boot partition")
        print("         sgdisk --new=3:0:0 --typecode=3:bf00 /dev/sdX      # ZFS partition")
        
        input("\nPress Enter when you have created the partitions...")
        
        # Refresh partition information
        disk_info = self.get_disk_info(self.selected_disk)
        if not disk_info['partitions']:
            raise Exception("No partitions found. Please create the required partitions.")
        
        print("\nDetected partitions:")
        for part in disk_info['partitions']:
            print(f"  {part['name']} ({part['size']}) - {part.get('fstype', 'unknown')}")
        
        # Select EFI partition
        efi_choices = [Choice(p['name'], p['name']) for p in disk_info['partitions']]
        self.partitions['efi'] = inquirer.select(
            message="Select the EFI System Partition:",
            choices=efi_choices
        ).execute()
        
        # Format EFI partition
        confirm = inquirer.confirm(
            message=f"Format {self.partitions['efi']} as FAT32 (required for EFI)?",
            default=True
        ).execute()
        if confirm:
            subprocess.run(["mkfs.fat", "-F32", self.partitions['efi']], check=True)
        
        # Ask if separate /boot partition is being used
        use_boot = inquirer.confirm(
            message="Are you using a separate /boot partition?",
            default=self.use_separate_boot
        ).execute()
        
        if use_boot:
            # Select boot partition
            remaining_parts = [p['name'] for p in disk_info['partitions'] if p['name'] != self.partitions['efi']]
            boot_choices = [Choice(p, p) for p in remaining_parts]
            self.partitions['boot'] = inquirer.select(
                message="Select the boot partition:",
                choices=boot_choices
            ).execute()
            
            # Format boot partition
            confirm = inquirer.confirm(
                message=f"Format {self.partitions['boot']} as ext4?",
                default=True
            ).execute()
            if confirm:
                subprocess.run(["mkfs.ext4", self.partitions['boot']], check=True)
            
            # Select ZFS partition
            remaining_parts = [p for p in remaining_parts if p != self.partitions['boot']]
            zfs_choices = [Choice(p, p) for p in remaining_parts]
            self.partitions['zfs'] = inquirer.select(
                message="Select the ZFS partition:",
                choices=zfs_choices
            ).execute()
        else:
            # Select ZFS partition
            remaining_parts = [p['name'] for p in disk_info['partitions'] if p['name'] != self.partitions['efi']]
            zfs_choices = [Choice(p, p) for p in remaining_parts]
            self.partitions['zfs'] = inquirer.select(
                message="Select the ZFS partition:",
                choices=zfs_choices
            ).execute()
    
    def _select_existing_partitions(self):
        """Use existing partitions for installation"""
        print("\nUsing existing partitions.")
        
        # Refresh partition information
        disk_info = self.get_disk_info(self.selected_disk)
        if not disk_info['partitions']:
            raise Exception("No partitions found. Cannot continue with existing partitions.")
        
        print("\nDetected partitions:")
        for part in disk_info['partitions']:
            print(f"  {part['name']} ({part['size']}) - {part.get('fstype', 'unknown')}")
        
        # Select EFI partition
        efi_choices = [Choice(p['name'], p['name']) for p in disk_info['partitions']]
        self.partitions['efi'] = inquirer.select(
            message="Select the EFI System Partition:",
            choices=efi_choices
        ).execute()
        
        # Check if EFI partition is formatted
        cmd = ["blkid", "-o", "value", "-s", "TYPE", self.partitions['efi']]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if "vfat" not in result.stdout.lower():
            print(f"Warning: {self.partitions['efi']} is not formatted as FAT32")
            confirm = inquirer.confirm(
                message="Format as FAT32 (required for EFI)?",
                default=True
            ).execute()
            if confirm:
                subprocess.run(["mkfs.fat", "-F32", self.partitions['efi']], check=True)
        
        # Ask if separate /boot partition is being used
        use_boot = inquirer.confirm(
            message="Are you using a separate /boot partition?",
            default=self.use_separate_boot
        ).execute()
        
        if use_boot:
            # Select boot partition
            remaining_parts = [p['name'] for p in disk_info['partitions'] if p['name'] != self.partitions['efi']]
            boot_choices = [Choice(p, p) for p in remaining_parts]
            self.partitions['boot'] = inquirer.select(
                message="Select the boot partition:",
                choices=boot_choices
            ).execute()
            
            # Select ZFS partition
            remaining_parts = [p for p in remaining_parts if p != self.partitions['boot']]
            zfs_choices = [Choice(p, p) for p in remaining_parts]
            self.partitions['zfs'] = inquirer.select(
                message="Select the ZFS partition:",
                choices=zfs_choices
            ).execute()
        else:
            # Select ZFS partition
            remaining_parts = [p['name'] for p in disk_info['partitions'] if p['name'] != self.partitions['efi']]
            zfs_choices = [Choice(p, p) for p in remaining_parts]
            self.partitions['zfs'] = inquirer.select(
                message="Select the ZFS partition:",
                choices=zfs_choices
            ).execute() 