#!/usr/bin/env python3
# Boot Manager Module
# Handles bootloader installation and configuration

import os
import subprocess
import shutil
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

class BootManager:
    def __init__(self):
        self.bootloader = "grub"
        self.kernel = "linux-lts"
        self.efi_partition = None
        self.boot_partition = None
        self.zfs_dataset = None
        self.pool_name = None
        self.root_mount = "/mnt"
        self.separate_boot = False
        self.dual_boot = False
    
    def setup_boot_partitions(self):
        """Configure boot-related settings"""
        print("\nBoot Configuration")
        print("=================")
        
        # Select bootloader
        self.bootloader = inquirer.select(
            message="Select bootloader:",
            choices=[
                Choice("grub", "GRUB (recommended, best ZFS support)"),
                Choice("systemd-boot", "systemd-boot (simpler, may require separate /boot)")
            ],
            default="grub"
        ).execute()
        
        # Select kernel
        self.kernel = inquirer.select(
            message="Select kernel package:",
            choices=[
                Choice("linux", "linux (standard kernel)"),
                Choice("linux-lts", "linux-lts (long-term support)"),
                Choice("linux-zen", "linux-zen (optimized kernel)")
            ],
            default="linux-lts"
        ).execute()
        
        # Check for dual-boot
        self.dual_boot = inquirer.confirm(
            message="Set up for dual-boot with Windows/other OS?",
            default=False
        ).execute()
        
        return {
            'bootloader': self.bootloader,
            'kernel': self.kernel,
            'dual_boot': self.dual_boot
        }
    
    def install_bootloader(self):
        """Install selected bootloader in the chroot environment"""
        print(f"\nInstalling {self.bootloader} bootloader...")
        
        if self.bootloader == "grub":
            self._install_grub()
        elif self.bootloader == "systemd-boot":
            self._install_systemd_boot()
    
    def _install_grub(self):
        """Install and configure GRUB bootloader"""
        try:
            # Install required packages
            cmd = ["arch-chroot", self.root_mount, "pacman", "-S", "--noconfirm", "grub", "efibootmgr", "dosfstools"]
            if self.dual_boot:
                cmd.append("os-prober")
            subprocess.run(cmd, check=True)
            
            # Create EFI directory if it doesn't exist
            efi_dir = os.path.join(self.root_mount, "boot/efi")
            os.makedirs(efi_dir, exist_ok=True)
            
            # Generate GRUB configuration for ZFS
            print("Updating GRUB configuration...")
            
            # Add ZFS to GRUB_PRELOAD_MODULES in /etc/default/grub
            grub_default_path = os.path.join(self.root_mount, "etc/default/grub")
            grub_lines = []
            if os.path.exists(grub_default_path):
                with open(grub_default_path, "r") as f:
                    grub_lines = f.readlines()
            
            # Modify or add GRUB_PRELOAD_MODULES
            module_line_exists = False
            for i, line in enumerate(grub_lines):
                if line.startswith("GRUB_PRELOAD_MODULES="):
                    if "zfs" not in line:
                        # Add zfs to existing modules
                        modules = line.split("=")[1].strip().strip('"\'')
                        modules = f"{modules} zfs"
                        grub_lines[i] = f'GRUB_PRELOAD_MODULES="{modules}"\n'
                    module_line_exists = True
                    break
            
            if not module_line_exists:
                grub_lines.append('GRUB_PRELOAD_MODULES="part_gpt zfs"\n')
            
            # Update GRUB_CMDLINE_LINUX to include ZFS parameters
            cmdline_exists = False
            for i, line in enumerate(grub_lines):
                if line.startswith("GRUB_CMDLINE_LINUX="):
                    cmdline = line.split("=")[1].strip().strip('"\'')
                    if "zfs=" not in cmdline:
                        cmdline = f"{cmdline} zfs={self.pool_name}/ROOT/arch"
                        grub_lines[i] = f'GRUB_CMDLINE_LINUX="{cmdline}"\n'
                    cmdline_exists = True
                    break
            
            if not cmdline_exists:
                grub_lines.append(f'GRUB_CMDLINE_LINUX="zfs={self.pool_name}/ROOT/arch"\n')
            
            # Enable os-prober if dual-booting
            if self.dual_boot:
                os_prober_exists = False
                for i, line in enumerate(grub_lines):
                    if line.startswith("GRUB_DISABLE_OS_PROBER="):
                        grub_lines[i] = 'GRUB_DISABLE_OS_PROBER=false\n'
                        os_prober_exists = True
                        break
                
                if not os_prober_exists:
                    grub_lines.append('GRUB_DISABLE_OS_PROBER=false\n')
            
            # Write updated GRUB configuration
            with open(grub_default_path, "w") as f:
                f.writelines(grub_lines)
            
            # Install GRUB
            cmd = [
                "arch-chroot", self.root_mount,
                "grub-install",
                "--target=x86_64-efi",
                "--efi-directory=/boot/efi",
                "--bootloader-id=GRUB"
            ]
            subprocess.run(cmd, check=True)
            
            # Generate GRUB configuration
            subprocess.run(["arch-chroot", self.root_mount, "grub-mkconfig", "-o", "/boot/grub/grub.cfg"], check=True)
            
            print("GRUB bootloader installed successfully.")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error installing GRUB: {e}")
    
    def _install_systemd_boot(self):
        """Install and configure systemd-boot"""
        try:
            # Install required packages
            cmd = ["arch-chroot", self.root_mount, "pacman", "-S", "--noconfirm", "efibootmgr", "dosfstools"]
            subprocess.run(cmd, check=True)
            
            # Install systemd-boot
            subprocess.run(["arch-chroot", self.root_mount, "bootctl", "install"], check=True)
            
            # Create loader configuration
            loader_path = os.path.join(self.root_mount, "boot/loader/loader.conf")
            with open(loader_path, "w") as f:
                f.write("default arch.conf\n")
                f.write("timeout 4\n")
                f.write("console-mode max\n")
                f.write("editor no\n")
            
            # Create arch.conf entry
            entries_dir = os.path.join(self.root_mount, "boot/loader/entries")
            os.makedirs(entries_dir, exist_ok=True)
            
            arch_conf_path = os.path.join(entries_dir, "arch.conf")
            with open(arch_conf_path, "w") as f:
                f.write("title Arch Linux (ZFS)\n")
                f.write(f"linux /vmlinuz-{self.kernel}\n")
                f.write(f"initrd /initramfs-{self.kernel}.img\n")
                f.write(f"options zfs={self.pool_name}/ROOT/arch rw\n")
            
            print("systemd-boot installed successfully.")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error installing systemd-boot: {e}")
    
    def setup_boot_directories(self, root_mount, pool_name, efi_partition, boot_partition=None):
        """Set up boot directories and store information"""
        self.root_mount = root_mount
        self.pool_name = pool_name
        self.efi_partition = efi_partition
        self.boot_partition = boot_partition
        self.separate_boot = boot_partition is not None
        
        # Create EFI mountpoint
        efi_dir = os.path.join(root_mount, "boot/efi")
        os.makedirs(efi_dir, exist_ok=True)
        
        # Mount EFI partition
        try:
            subprocess.run(["mount", efi_partition, efi_dir], check=True)
            print(f"Mounted EFI partition at {efi_dir}")
            
            # If using separate boot partition, mount it
            if self.separate_boot:
                boot_dir = os.path.join(root_mount, "boot")
                subprocess.run(["mount", boot_partition, boot_dir], check=True)
                print(f"Mounted boot partition at {boot_dir}")
                
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error mounting boot partitions: {e}")
    
    def generate_fstab(self):
        """Generate fstab entries for boot partitions"""
        fstab_path = os.path.join(self.root_mount, "etc/fstab")
        
        with open(fstab_path, "a") as f:
            # Add EFI partition
            f.write(f"{self.efi_partition}\t/boot/efi\tvfat\tdefaults,noatime\t0 2\n")
            
            # Add separate boot partition if used
            if self.separate_boot:
                f.write(f"{self.boot_partition}\t/boot\text4\tdefaults,noatime\t0 2\n")
            
            # Add swap if available
            swap_device = f"/dev/zvol/{self.pool_name}/swap"
            if os.path.exists(swap_device):
                f.write(f"{swap_device}\tnone\tswap\tdefaults\t0 0\n")
        
        print("Boot entries added to fstab.")
    
    def configure_initramfs(self):
        """Configure the initramfs to include ZFS support"""
        print("Configuring initramfs with ZFS support...")
        
        # Update mkinitcpio.conf
        mkinitcpio_path = os.path.join(self.root_mount, "etc/mkinitcpio.conf")
        mkinitcpio_lines = []
        
        if os.path.exists(mkinitcpio_path):
            with open(mkinitcpio_path, "r") as f:
                mkinitcpio_lines = f.readlines()
        
        # Update HOOKS line to include ZFS
        for i, line in enumerate(mkinitcpio_lines):
            if line.startswith("HOOKS="):
                hooks = line.split("=")[1].strip().strip('()"\'')
                hooks_list = hooks.split()
                
                # Check if we need to add zfs
                if "zfs" not in hooks_list:
                    # Add zfs before filesystems
                    if "filesystems" in hooks_list:
                        idx = hooks_list.index("filesystems")
                        hooks_list.insert(idx, "zfs")
                    else:
                        # If filesystems isn't there, add zfs near the end
                        hooks_list.append("zfs")
                
                # Ensure other necessary hooks are present
                for hook in ["keyboard", "keymap", "encrypt", "sd-vconsole", "sd-encrypt"]:
                    if self.bootloader == "systemd-boot" and hook.startswith("sd-"):
                        if hook not in hooks_list:
                            hooks_list.append(hook)
                
                # Update the line
                mkinitcpio_lines[i] = f'HOOKS=({" ".join(hooks_list)})\n'
                break
        
        # Update MODULES line to include necessary modules
        for i, line in enumerate(mkinitcpio_lines):
            if line.startswith("MODULES="):
                # Keep existing modules and add those needed for ZFS
                modules = line.split("=")[1].strip().strip('()"\'')
                modules_list = modules.split()
                
                # Add modules needed for ZFS
                for module in ["zfs"]:
                    if module not in modules_list:
                        modules_list.append(module)
                
                # Update the line
                mkinitcpio_lines[i] = f'MODULES=({" ".join(modules_list)})\n'
                break
        
        # Write updated mkinitcpio.conf
        with open(mkinitcpio_path, "w") as f:
            f.writelines(mkinitcpio_lines)
        
        # Generate initramfs
        try:
            subprocess.run(["arch-chroot", self.root_mount, "mkinitcpio", "-P"], check=True)
            print("Initramfs generated with ZFS support.")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error generating initramfs: {e}")
    
    def unmount_boot(self):
        """Unmount boot partitions"""
        try:
            # Unmount EFI partition
            efi_dir = os.path.join(self.root_mount, "boot/efi")
            subprocess.run(["umount", efi_dir], check=True)
            
            # Unmount separate boot partition if it exists
            if self.separate_boot:
                boot_dir = os.path.join(self.root_mount, "boot")
                subprocess.run(["umount", boot_dir], check=True)
            
            print("Boot partitions unmounted.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to unmount boot partitions: {e}")
            return False 