#!/usr/bin/env python3
# Installer Module
# Main installation logic for Arch Linux with ZFS

import os
import time
import subprocess
import shutil
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

class Installer:
    def __init__(self, disk_manager, zfs_manager, boot_manager, system_config):
        self.disk_manager = disk_manager
        self.zfs_manager = zfs_manager
        self.boot_manager = boot_manager
        self.system_config = system_config
        self.root_mount = "/mnt"
        self.installation_complete = False
    
    def mount_filesystems(self):
        """Mount all filesystems for installation"""
        print("\nMounting filesystems...")
        
        # Import ZFS pool
        self.zfs_manager.import_pool(mount=False)
        
        # Create mountpoint
        os.makedirs(self.root_mount, exist_ok=True)
        
        # Mount root dataset
        root_dataset = self.zfs_manager.datasets['root']
        try:
            # Set mountpoint for root dataset
            subprocess.run(["zfs", "set", f"mountpoint={self.root_mount}", root_dataset], check=True)
            
            # Mount root dataset
            subprocess.run(["zfs", "mount", root_dataset], check=True)
            
            # Mount other datasets
            for dataset, mountpoint in [
                (f"{self.zfs_manager.pool_name}/home", f"{self.root_mount}/home"),
                (f"{self.zfs_manager.pool_name}/var", f"{self.root_mount}/var"),
                (f"{self.zfs_manager.pool_name}/var/log", f"{self.root_mount}/var/log"),
                (f"{self.zfs_manager.pool_name}/var/cache", f"{self.root_mount}/var/cache")
            ]:
                # Ensure parent directory exists
                parent_dir = os.path.dirname(mountpoint)
                if parent_dir != self.root_mount:
                    os.makedirs(parent_dir, exist_ok=True)
                
                # Set mountpoint and mount
                subprocess.run(["zfs", "set", f"mountpoint={mountpoint}", dataset], check=True)
                subprocess.run(["zfs", "mount", dataset], check=True)
            
            print("ZFS datasets mounted successfully.")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error mounting ZFS datasets: {e}")
        
        # Mount boot partitions
        self.boot_manager.setup_boot_directories(
            self.root_mount,
            self.zfs_manager.pool_name,
            self.disk_manager.partitions['efi'],
            self.disk_manager.partitions.get('boot')
        )
    
    def install_base_system(self):
        """Install the base Arch Linux system"""
        print("\nInstalling base system...")
        
        # Update pacman mirrorlist if needed
        self._update_mirrorlist()
        
        # Prepare package list
        base_packages = ["base", "base-devel"]
        
        # Add kernel and firmware
        kernel_packages = [self.boot_manager.kernel, f"{self.boot_manager.kernel}-headers", "linux-firmware"]
        
        # Add ZFS packages
        zfs_packages = [f"zfs-{self.boot_manager.kernel}", "zfs-utils"]
        
        # Add other essential packages
        essential_packages = [
            "vim", "nano",             # Editors
            "networkmanager",          # Network management
            "dhcpcd",                  # DHCP client
            "man-db", "man-pages",     # Documentation
            "which", "wget", "curl",   # Utilities
            "tar", "gzip", "unzip",    # Archive utilities
            "python", "python-pip"     # Python
        ]
        
        # Additional optional packages
        additional_packages = inquirer.checkbox(
            message="Select additional packages to install:",
            choices=[
                Choice("git", "Git version control"),
                Choice("openssh", "SSH server and client"),
                Choice("htop", "Interactive process viewer"),
                Choice("reflector", "Mirrorlist manager"),
                Choice("dialog", "Dialog utility"),
                Choice("lsof", "List open files"),
                Choice("intel-ucode", "Intel CPU microcode updates"),
                Choice("amd-ucode", "AMD CPU microcode updates")
            ]
        ).execute()
        
        # Combine all packages
        packages = base_packages + kernel_packages + zfs_packages + essential_packages + additional_packages
        
        # Install packages
        try:
            print(f"Installing packages: {', '.join(packages)}")
            
            # Use custom IFS in pacstrap to avoid command line length issues
            pacstrap_env = os.environ.copy()
            pacstrap_env["IFS"] = ' '
            
            cmd = ["pacstrap", self.root_mount] + packages
            subprocess.run(cmd, check=True, env=pacstrap_env)
            
            print("Base system installed successfully.")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error installing base system: {e}")
    
    def _update_mirrorlist(self):
        """Update pacman mirrorlist for faster downloads"""
        update_mirrors = inquirer.confirm(
            message="Update pacman mirrorlist for faster downloads?",
            default=True
        ).execute()
        
        if update_mirrors:
            country = inquirer.select(
                message="Select your country/region for mirrors:",
                choices=[
                    Choice("US", "United States"),
                    Choice("UK", "United Kingdom"),
                    Choice("DE", "Germany"),
                    Choice("FR", "France"),
                    Choice("AU", "Australia"),
                    Choice("JP", "Japan"),
                    Choice("KR", "South Korea"),
                    Choice("CA", "Canada"),
                    Choice("all", "All mirrors (sorted by speed)")
                ],
                default="US"
            ).execute()
            
            try:
                print("Updating mirrorlist...")
                
                # Create backup of existing mirrorlist
                mirrorlist_path = "/etc/pacman.d/mirrorlist"
                if os.path.exists(mirrorlist_path):
                    shutil.copy(mirrorlist_path, f"{mirrorlist_path}.backup")
                
                if country == "all":
                    # Use reflector to sort all mirrors by speed
                    subprocess.run([
                        "reflector", "--latest", "50",
                        "--sort", "rate",
                        "--save", mirrorlist_path
                    ], check=True)
                else:
                    # Filter by country and sort by speed
                    subprocess.run([
                        "reflector", "--country", country,
                        "--latest", "20",
                        "--sort", "rate",
                        "--save", mirrorlist_path
                    ], check=True)
                
                print(f"Mirrorlist updated with mirrors from {country}.")
                
            except subprocess.CalledProcessError as e:
                print(f"Warning: Error updating mirrorlist: {e}")
                print("Continuing with existing mirrorlist.")
    
    def generate_fstab(self):
        """Generate fstab file"""
        print("Generating fstab...")
        
        try:
            # Create fstab directory if it doesn't exist
            os.makedirs(os.path.join(self.root_mount, "etc"), exist_ok=True)
            
            # Generate fstab file
            fstab_path = os.path.join(self.root_mount, "etc/fstab")
            
            # Backup existing fstab if it exists
            if os.path.exists(fstab_path):
                shutil.copy(fstab_path, f"{fstab_path}.backup")
            
            # Create basic fstab
            with open(fstab_path, "w") as f:
                f.write("# /etc/fstab: static file system information\n")
                f.write("# <file system>\t<dir>\t<type>\t<options>\t<dump>\t<pass>\n\n")
                
                # Add tmpfs for /tmp
                f.write("tmpfs\t/tmp\ttmpfs\tdefaults,nosuid,nodev\t0 0\n")
            
            # Add boot entries to fstab
            self.boot_manager.generate_fstab()
            
            print("Fstab generated successfully.")
            
        except Exception as e:
            print(f"Warning: Error generating fstab: {e}")
    
    def setup_zfs_cache(self):
        """Create ZFS cache files"""
        print("Creating ZFS cache files...")
        
        try:
            # Create zfs cache directory
            os.makedirs(os.path.join(self.root_mount, "etc/zfs"), exist_ok=True)
            
            # Export pool to generate cache
            self.zfs_manager.export_pool()
            
            # Re-import pool with cache generation
            subprocess.run([
                "zpool", "import",
                "-d", "/dev/disk/by-id",
                "-f", "-N", "-o", "cachefile=/etc/zfs/zpool.cache",
                self.zfs_manager.pool_name
            ], check=True)
            
            # Copy cache file to installed system
            shutil.copy("/etc/zfs/zpool.cache", os.path.join(self.root_mount, "etc/zfs/zpool.cache"))
            
            # Copy zfs module directory if it exists
            zfs_module_dir = "/lib/modules"
            if os.path.exists(zfs_module_dir):
                shutil.copytree(
                    zfs_module_dir,
                    os.path.join(self.root_mount, "lib/modules"),
                    dirs_exist_ok=True
                )
            
            # Import the pool again for mounting
            self.zfs_manager.import_pool(mount=True)
            
            print("ZFS cache files created successfully.")
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Warning: Error creating ZFS cache files: {e}")
    
    def configure_bootloader(self):
        """Configure bootloader"""
        print("Configuring bootloader...")
        
        # Configure initramfs for ZFS
        self.boot_manager.configure_initramfs()
        
        # Install bootloader
        self.boot_manager.install_bootloader()
    
    def finalize_installation(self):
        """Finalize the installation"""
        print("\nFinalizing installation...")
        
        # Generate fstab
        self.generate_fstab()
        
        # Set up ZFS cache
        self.setup_zfs_cache()
        
        # Configure bootloader
        self.configure_bootloader()
        
        # Set system configuration variables
        self.system_config.set_root_mount(self.root_mount)
        
        # Configure system
        self.system_config.configure_system()
        
        # Unmount filesystems
        self._unmount_filesystems()
        
        self.installation_complete = True
        print("\n" + "=" * 80)
        print("Arch Linux with ZFS installation completed!")
        print("=" * 80)
        print("\nYou can now reboot into your new system.")
        print("\nRemember to export the ZFS pool before rebooting:")
        print(f"  # zpool export {self.zfs_manager.pool_name}")
    
    def _unmount_filesystems(self):
        """Unmount all filesystems"""
        print("Unmounting filesystems...")
        
        # Unmount boot partitions
        self.boot_manager.unmount_boot()
        
        # Unmount ZFS datasets
        try:
            # Unmount in reverse order of mounting
            datasets = [
                f"{self.zfs_manager.pool_name}/var/cache",
                f"{self.zfs_manager.pool_name}/var/log",
                f"{self.zfs_manager.pool_name}/var/cache",
                f"{self.zfs_manager.pool_name}/var",
                f"{self.zfs_manager.pool_name}/home",
                self.zfs_manager.datasets['root']
            ]
            
            for dataset in datasets:
                try:
                    subprocess.run(["zfs", "unmount", dataset], check=False)
                except subprocess.CalledProcessError:
                    pass  # Ignore errors
            
            # Export the pool
            if inquirer.confirm(
                message="Export ZFS pool now?",
                default=True
            ).execute():
                self.zfs_manager.export_pool()
            
        except Exception as e:
            print(f"Warning: Error unmounting ZFS datasets: {e}")
            print("You may need to manually unmount them before rebooting.")
            
        print("Filesystems unmounted.")
    
    def cleanup(self):
        """Clean up temporary files and mount points"""
        if not self.installation_complete:
            # Only run cleanup if installation wasn't completed
            print("Cleaning up...")
            
            # Unmount all filesystems
            self._unmount_filesystems()
            
            # Remove the root mount point if it's empty
            try:
                os.rmdir(self.root_mount)
            except (OSError, FileNotFoundError):
                pass 