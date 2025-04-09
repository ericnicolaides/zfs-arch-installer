#!/usr/bin/env python3
# ZFS Manager Module
# Handles ZFS pool and dataset operations

import os
import subprocess
import random
import string
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

class ZFSManager:
    def __init__(self):
        self.pool_name = "rpool"
        self.pool_type = "single"
        self.disks = []
        self.compression = "lz4"
        self.deduplication = False
        self.encryption = False
        self.encryption_passphrase = ""
        self.ashift = 12
        self.autotrim = True
        self.swap_size = 0
        self.datasets = {}
    
    def setup_pool(self):
        """Set up ZFS pool configuration"""
        print("\nZFS Pool Configuration")
        print("=====================")
        
        # Pool name
        self.pool_name = inquirer.text(
            message="Enter ZFS pool name:",
            default="rpool",
            validate=lambda text: len(text) > 0 and " " not in text
        ).execute()
        
        # Pool layout/type
        self.pool_type = inquirer.select(
            message="Select pool layout:",
            choices=[
                Choice("single", "Single disk (no redundancy)"),
                Choice("mirror", "Mirror (RAID1, 2+ disks)"),
                Choice("raidz1", "RAIDZ1 (RAID5, 3+ disks)"),
                Choice("raidz2", "RAIDZ2 (RAID6, 4+ disks)")
            ],
            default="single"
        ).execute()
        
        # Compression
        self.compression = inquirer.select(
            message="Select compression algorithm:",
            choices=[
                Choice("lz4", "lz4 (fast, recommended)"),
                Choice("zstd", "zstd (better compression but more CPU)"),
                Choice("off", "No compression")
            ],
            default="lz4"
        ).execute()
        
        # Deduplication
        self.deduplication = inquirer.confirm(
            message="Enable deduplication? (NOT recommended for most systems)",
            default=False
        ).execute()
        
        # Encryption
        self.encryption = inquirer.confirm(
            message="Enable native ZFS encryption?",
            default=True
        ).execute()
        
        if self.encryption:
            self.encryption_passphrase = inquirer.secret(
                message="Enter encryption passphrase:",
                validate=lambda text: len(text) >= 8
            ).execute()
            
            # Confirm passphrase
            confirm_passphrase = inquirer.secret(
                message="Confirm encryption passphrase:",
            ).execute()
            
            if confirm_passphrase != self.encryption_passphrase:
                raise Exception("Passphrases do not match")
        
        # Advanced options
        advanced = inquirer.confirm(
            message="Configure advanced ZFS options?",
            default=False
        ).execute()
        
        if advanced:
            # ashift
            self.ashift = inquirer.select(
                message="Select ashift value:",
                choices=[
                    Choice(9, "ashift=9 (512B sectors, older HDDs)"),
                    Choice(12, "ashift=12 (4K sectors, modern drives)"),
                    Choice(13, "ashift=13 (8K sectors, some enterprise drives)")
                ],
                default=12
            ).execute()
            
            # autotrim
            self.autotrim = inquirer.confirm(
                message="Enable autotrim? (recommended for SSDs)",
                default=True
            ).execute()
        
        # Swap size
        use_swap = inquirer.confirm(
            message="Create a swap ZVOL?",
            default=True
        ).execute()
        
        if use_swap:
            memory_size = self._get_memory_size()
            default_swap = min(max(memory_size // 2, 2), 32)  # Between 2G and 32G
            
            self.swap_size = inquirer.number(
                message="Enter swap size in GiB:",
                min_allowed=1,
                max_allowed=128,
                default=default_swap,
                float_allowed=False
            ).execute()
        
        return {
            'pool_name': self.pool_name,
            'pool_type': self.pool_type,
            'compression': self.compression,
            'deduplication': self.deduplication,
            'encryption': self.encryption,
            'ashift': self.ashift,
            'autotrim': self.autotrim,
            'swap_size': self.swap_size
        }
    
    def create_pool(self, zfs_partitions):
        """Create the ZFS pool with the specified configuration"""
        print(f"\nCreating ZFS pool '{self.pool_name}'...")
        
        # Convert single partition to list if needed
        if isinstance(zfs_partitions, str):
            zfs_partitions = [zfs_partitions]
        
        # Prepare pool creation command
        cmd = ["zpool", "create", "-f"]
        
        # Add ashift
        cmd.extend(["-o", f"ashift={self.ashift}"])
        
        # Add autotrim if enabled
        if self.autotrim:
            cmd.extend(["-o", "autotrim=on"])
        
        # Add basic options
        cmd.extend([
            "-O", "compression=" + self.compression,
            "-O", "normalization=formD",
            "-O", "acltype=posixacl",
            "-O", "xattr=sa",
            "-O", "relatime=on",
            "-O", "canmount=off"
        ])
        
        # Add deduplication if enabled
        if self.deduplication:
            cmd.extend(["-O", "dedup=on"])
        
        # Add encryption if enabled
        if self.encryption:
            cmd.extend([
                "-O", "encryption=aes-256-gcm",
                "-O", "keylocation=prompt",
                "-O", "keyformat=passphrase"
            ])
        
        # Add mountpoint
        cmd.extend(["-O", f"mountpoint=none"])
        
        # Add pool name
        cmd.append(self.pool_name)
        
        # Add pool type and disks
        if self.pool_type == "single" or len(zfs_partitions) == 1:
            cmd.append(zfs_partitions[0])
        elif self.pool_type == "mirror":
            cmd.append("mirror")
            cmd.extend(zfs_partitions)
        elif self.pool_type.startswith("raidz"):
            cmd.append(self.pool_type)
            cmd.extend(zfs_partitions)
        
        # Create the pool
        try:
            if self.encryption:
                # For encryption, we need to provide the passphrase via stdin
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(input=self.encryption_passphrase + "\n")
                
                if proc.returncode != 0:
                    raise Exception(f"Failed to create encrypted ZFS pool: {stderr}")
            else:
                subprocess.run(cmd, check=True)
            
            print(f"ZFS pool '{self.pool_name}' created successfully.")
            return True
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error creating ZFS pool: {e}")
    
    def create_datasets(self):
        """Create ZFS datasets with appropriate options"""
        print("\nCreating ZFS datasets...")
        
        # Create basic dataset structure
        self._create_dataset(f"{self.pool_name}/ROOT", "canmount=off", "mountpoint=none")
        
        # Generate a unique dataset name with creation time
        root_ds_name = f"{self.pool_name}/ROOT/arch"
        
        # Create root dataset
        self._create_dataset(
            root_ds_name,
            "canmount=noauto",
            "mountpoint=/",
            "com.sun:auto-snapshot=true"
        )
        
        # Create home dataset
        self._create_dataset(
            f"{self.pool_name}/home",
            "mountpoint=/home",
            "com.sun:auto-snapshot=true"
        )
        
        # Create other useful datasets
        self._create_dataset(f"{self.pool_name}/var", "mountpoint=/var", "com.sun:auto-snapshot=false")
        self._create_dataset(f"{self.pool_name}/var/log", "mountpoint=/var/log")
        self._create_dataset(f"{self.pool_name}/var/cache", "mountpoint=/var/cache")
        
        # Create swap volume if requested
        if self.swap_size > 0:
            self._create_swap_zvol()
        
        # Set bootfs property
        subprocess.run(["zpool", "set", f"bootfs={root_ds_name}", self.pool_name], check=True)
        
        self.datasets = {
            'root': root_ds_name,
            'home': f"{self.pool_name}/home",
            'var': f"{self.pool_name}/var",
            'swap': f"{self.pool_name}/swap" if self.swap_size > 0 else None
        }
        
        print("ZFS datasets created successfully.")
        return self.datasets
    
    def _create_dataset(self, name, *properties):
        """Create a ZFS dataset with the given properties"""
        cmd = ["zfs", "create", "-p"]
        
        # Add properties
        for prop in properties:
            cmd.extend(["-o", prop])
        
        # Add dataset name
        cmd.append(name)
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error creating dataset {name}: {e}")
    
    def _create_swap_zvol(self):
        """Create a ZFS volume for swap"""
        swap_size_bytes = self.swap_size * 1024 * 1024 * 1024  # Convert GiB to bytes
        
        try:
            # Create swap volume
            cmd = [
                "zfs", "create",
                "-V", str(swap_size_bytes),
                "-b", "4K",
                "-o", "compression=zle",
                "-o", "logbias=throughput",
                "-o", "sync=always",
                "-o", "primarycache=metadata",
                "-o", "com.sun:auto-snapshot=false",
                f"{self.pool_name}/swap"
            ]
            subprocess.run(cmd, check=True)
            
            # Format swap
            swap_device = f"/dev/zvol/{self.pool_name}/swap"
            subprocess.run(["mkswap", "-f", swap_device], check=True)
            
            print(f"Created and formatted swap volume: {swap_device}")
            return swap_device
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error creating swap volume: {e}")
    
    def _get_memory_size(self):
        """Get system memory size in GiB"""
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # Extract memory in KB, convert to GB
                        mem_kb = int(line.split()[1])
                        mem_gb = mem_kb // (1024 * 1024)
                        return max(mem_gb, 1)  # At least 1 GB
        except Exception:
            # Default to 8 GB if we can't determine
            return 8
    
    def generate_hostid(self):
        """Generate a random hostid for ZFS if needed"""
        try:
            # Check if hostid exists
            if not os.path.exists("/etc/hostid"):
                print("Generating ZFS hostid...")
                # Generate random 4-byte hostid
                hostid = ''.join(random.choices('0123456789abcdef', k=8))
                subprocess.run(["zgenhostid", hostid], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to generate hostid: {e}")
    
    def export_pool(self):
        """Export the ZFS pool, required before rebooting"""
        try:
            subprocess.run(["zpool", "export", self.pool_name], check=True)
            print(f"ZFS pool '{self.pool_name}' exported successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to export pool: {e}")
            return False
    
    def import_pool(self, mount=True):
        """Import the ZFS pool with options"""
        try:
            cmd = ["zpool", "import", "-d", "/dev/disk/by-id", "-f"]
            if not mount:
                cmd.append("-N")
            cmd.append(self.pool_name)
            
            if self.encryption:
                # For encryption, we need to provide the passphrase
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(input=self.encryption_passphrase + "\n")
                
                if proc.returncode != 0:
                    raise Exception(f"Failed to import encrypted ZFS pool: {stderr}")
            else:
                subprocess.run(cmd, check=True)
            
            print(f"ZFS pool '{self.pool_name}' imported successfully.")
            return True
            
        except Exception as e:
            print(f"Warning: Failed to import pool: {e}")
            return False 