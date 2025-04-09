#!/usr/bin/env python3
# System Configuration Module
# Handles system configuration tasks for Arch Linux

import os
import subprocess
import shutil
import re
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

class SystemConfig:
    def __init__(self):
        self.root_mount = "/mnt"
        self.locale = "en_US.UTF-8"
        self.keymap = "us"
        self.timezone = "UTC"
        self.hostname = "archzfs"
        self.users = []
        self.root_password = None
    
    def configure_system(self):
        """Configure basic system settings"""
        print("\nSystem Configuration")
        print("===================")
        
        self._configure_locale()
        self._configure_timezone()
        self._configure_network()
        self._configure_users()
        self._configure_services()
        
        print("\nSystem configuration completed.")
    
    def _configure_locale(self):
        """Configure system locale and keymap"""
        print("\nLocalization Settings")
        
        # Select locale
        locales = [
            Choice("en_US.UTF-8", "English (US)"),
            Choice("en_GB.UTF-8", "English (UK)"),
            Choice("de_DE.UTF-8", "German"),
            Choice("fr_FR.UTF-8", "French"),
            Choice("es_ES.UTF-8", "Spanish"),
            Choice("it_IT.UTF-8", "Italian"),
            Choice("ru_RU.UTF-8", "Russian"),
            Choice("zh_CN.UTF-8", "Chinese (Simplified)"),
            Choice("ja_JP.UTF-8", "Japanese")
        ]
        
        self.locale = inquirer.select(
            message="Select system locale:",
            choices=locales,
            default="en_US.UTF-8"
        ).execute()
        
        # Select keymap
        keymaps = [
            Choice("us", "US"),
            Choice("uk", "UK"),
            Choice("de", "German"),
            Choice("fr", "French"),
            Choice("es", "Spanish"),
            Choice("it", "Italian"),
            Choice("ru", "Russian")
        ]
        
        self.keymap = inquirer.select(
            message="Select keyboard layout:",
            choices=keymaps,
            default="us"
        ).execute()
        
        # Apply locale settings
        try:
            # Generate locale
            locale_gen_path = os.path.join(self.root_mount, "etc/locale.gen")
            locale_lines = []
            
            if os.path.exists(locale_gen_path):
                with open(locale_gen_path, "r") as f:
                    locale_lines = f.readlines()
            
            # Find locale line and uncomment it
            locale_found = False
            for i, line in enumerate(locale_lines):
                if self.locale in line and line.startswith("#"):
                    locale_lines[i] = line.lstrip("#")
                    locale_found = True
            
            if not locale_found:
                locale_lines.append(f"{self.locale} UTF-8\n")
            
            with open(locale_gen_path, "w") as f:
                f.writelines(locale_lines)
            
            # Generate locale
            subprocess.run(["arch-chroot", self.root_mount, "locale-gen"], check=True)
            
            # Set locale.conf
            locale_conf_path = os.path.join(self.root_mount, "etc/locale.conf")
            with open(locale_conf_path, "w") as f:
                f.write(f"LANG={self.locale}\n")
            
            # Set keymap
            vconsole_conf_path = os.path.join(self.root_mount, "etc/vconsole.conf")
            with open(vconsole_conf_path, "w") as f:
                f.write(f"KEYMAP={self.keymap}\n")
            
            print(f"Locale set to {self.locale} with {self.keymap} keymap.")
            
        except Exception as e:
            print(f"Warning: Error setting locale: {e}")
    
    def _configure_timezone(self):
        """Configure system timezone"""
        print("\nTimezone Settings")
        
        # Define common timezones as choices
        timezone_choices = [
            Choice("America/New_York", "Eastern Time (US)"),
            Choice("America/Chicago", "Central Time (US)"),
            Choice("America/Denver", "Mountain Time (US)"),
            Choice("America/Los_Angeles", "Pacific Time (US)"),
            Choice("Europe/London", "London"),
            Choice("Europe/Berlin", "Berlin/Paris/Rome"),
            Choice("Europe/Moscow", "Moscow"),
            Choice("Asia/Tokyo", "Tokyo"),
            Choice("Asia/Shanghai", "Shanghai"),
            Choice("Australia/Sydney", "Sydney"),
            Choice("UTC", "UTC (Universal Time)")
        ]
        
        # Ask for timezone
        self.timezone = inquirer.select(
            message="Select timezone:",
            choices=timezone_choices,
            default="UTC"
        ).execute()
        
        # Set timezone
        try:
            # Create symbolic link
            subprocess.run([
                "arch-chroot", self.root_mount,
                "ln", "-sf", f"/usr/share/zoneinfo/{self.timezone}", "/etc/localtime"
            ], check=True)
            
            # Set hardware clock
            subprocess.run([
                "arch-chroot", self.root_mount,
                "hwclock", "--systohc"
            ], check=True)
            
            print(f"Timezone set to {self.timezone}.")
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: Error setting timezone: {e}")
    
    def _configure_network(self):
        """Configure network settings"""
        print("\nNetwork Configuration")
        
        # Set hostname
        self.hostname = inquirer.text(
            message="Enter hostname:",
            default="archzfs",
            validate=lambda text: len(text) > 0 and " " not in text
        ).execute()
        
        # Set hostname
        hostname_path = os.path.join(self.root_mount, "etc/hostname")
        with open(hostname_path, "w") as f:
            f.write(f"{self.hostname}\n")
        
        # Set hosts file
        hosts_path = os.path.join(self.root_mount, "etc/hosts")
        with open(hosts_path, "w") as f:
            f.write("127.0.0.1\tlocalhost\n")
            f.write("::1\t\tlocalhost\n")
            f.write(f"127.0.1.1\t{self.hostname}.localdomain\t{self.hostname}\n")
        
        # Network management
        network_tools = inquirer.select(
            message="Select network management tool:",
            choices=[
                Choice("networkmanager", "NetworkManager (recommended for desktops)"),
                Choice("systemd-networkd", "systemd-networkd (minimal, good for servers)"),
                Choice("none", "None (manual configuration)")
            ],
            default="networkmanager"
        ).execute()
        
        if network_tools == "networkmanager":
            # Install NetworkManager
            subprocess.run([
                "arch-chroot", self.root_mount,
                "pacman", "-S", "--noconfirm", "networkmanager"
            ], check=True)
            
            # Enable service
            subprocess.run([
                "arch-chroot", self.root_mount,
                "systemctl", "enable", "NetworkManager"
            ], check=True)
            
        elif network_tools == "systemd-networkd":
            # Enable systemd-networkd and systemd-resolved
            subprocess.run([
                "arch-chroot", self.root_mount,
                "systemctl", "enable", "systemd-networkd"
            ], check=True)
            
            subprocess.run([
                "arch-chroot", self.root_mount,
                "systemctl", "enable", "systemd-resolved"
            ], check=True)
            
            # Create a basic network configuration
            network_dir = os.path.join(self.root_mount, "etc/systemd/network")
            os.makedirs(network_dir, exist_ok=True)
            
            # Create a basic DHCP configuration
            with open(os.path.join(network_dir, "20-wired.network"), "w") as f:
                f.write("[Match]\n")
                f.write("Name=en*\n\n")
                f.write("[Network]\n")
                f.write("DHCP=yes\n")
                f.write("IPv6PrivacyExtensions=yes\n")
        
        print(f"Network configured with hostname: {self.hostname}")
    
    def _configure_users(self):
        """Configure root password and user accounts"""
        print("\nUser Configuration")
        
        # Set root password
        print("\nSetting root password")
        self.root_password = inquirer.secret(
            message="Enter root password:",
            validate=lambda text: len(text) >= 6
        ).execute()
        
        # Confirm password
        confirm_password = inquirer.secret(
            message="Confirm root password:"
        ).execute()
        
        if confirm_password != self.root_password:
            print("Passwords do not match. Please try again.")
            return self._configure_users()
        
        # Set root password using chroot
        self._set_password("root", self.root_password)
        
        # Add additional users?
        create_user = inquirer.confirm(
            message="Create a regular user account?",
            default=True
        ).execute()
        
        if create_user:
            self._create_user()
        
        # Ask to create more users
        while inquirer.confirm(
            message="Create another user account?",
            default=False
        ).execute():
            self._create_user()
    
    def _create_user(self):
        """Create a new user account"""
        # Get username
        username = inquirer.text(
            message="Enter username:",
            validate=lambda text: re.match(r'^[a-z_][a-z0-9_-]*[$]?$', text) is not None
        ).execute()
        
        # Get password
        password = inquirer.secret(
            message=f"Enter password for {username}:",
            validate=lambda text: len(text) >= 6
        ).execute()
        
        # Confirm password
        confirm_password = inquirer.secret(
            message=f"Confirm password for {username}:"
        ).execute()
        
        if confirm_password != password:
            print("Passwords do not match. Please try again.")
            return self._create_user()
        
        # Select shell
        shell = inquirer.select(
            message="Select default shell:",
            choices=[
                Choice("/bin/bash", "Bash (default)"),
                Choice("/bin/zsh", "Zsh"),
                Choice("/bin/fish", "Fish")
            ],
            default="/bin/bash"
        ).execute()
        
        # Select groups
        default_groups = ["wheel", "audio", "video", "optical", "storage"]
        groups = inquirer.checkbox(
            message="Select user groups:",
            choices=[
                Choice("wheel", "wheel (sudo access)", True),
                Choice("audio", "audio", True),
                Choice("video", "video", True),
                Choice("optical", "optical", True),
                Choice("storage", "storage", True),
                Choice("network", "network"),
                Choice("games", "games"),
                Choice("docker", "docker")
            ]
        ).execute()
        
        if not groups:
            groups = default_groups
        
        # Create user
        try:
            # First install sudo if wheel group is used
            if "wheel" in groups:
                subprocess.run([
                    "arch-chroot", self.root_mount,
                    "pacman", "-S", "--noconfirm", "sudo"
                ], check=True)
                
                # Enable wheel group in sudoers
                sudoers_path = os.path.join(self.root_mount, "etc/sudoers.d/wheel")
                with open(sudoers_path, "w") as f:
                    f.write("%wheel ALL=(ALL) ALL\n")
                os.chmod(sudoers_path, 0o440)
            
            # Install shell if not bash
            if shell != "/bin/bash":
                shell_pkg = os.path.basename(shell)
                subprocess.run([
                    "arch-chroot", self.root_mount,
                    "pacman", "-S", "--noconfirm", shell_pkg
                ], check=True)
            
            # Create user
            cmd = [
                "arch-chroot", self.root_mount,
                "useradd", "-m", "-G", ",".join(groups), "-s", shell, username
            ]
            subprocess.run(cmd, check=True)
            
            # Set user password
            self._set_password(username, password)
            
            self.users.append({
                'username': username,
                'groups': groups,
                'shell': shell
            })
            
            print(f"User {username} created successfully.")
            
        except subprocess.CalledProcessError as e:
            print(f"Error creating user {username}: {e}")
    
    def _set_password(self, username, password):
        """Set password for a user using chroot and passwd"""
        try:
            # Use expect-like behavior with a pipe
            cmd = ["arch-chroot", self.root_mount, "passwd", username]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send password twice (for confirmation)
            stdout, stderr = proc.communicate(input=f"{password}\n{password}\n")
            
            if proc.returncode != 0:
                print(f"Warning: Error setting password for {username}: {stderr}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Warning: Error setting password for {username}: {e}")
            return False
    
    def _configure_services(self):
        """Enable essential services"""
        print("\nConfiguring system services...")
        
        # ZFS services
        zfs_services = ["zfs.target", "zfs-import-cache", "zfs-mount", "zfs-import.target"]
        
        for service in zfs_services:
            try:
                subprocess.run([
                    "arch-chroot", self.root_mount,
                    "systemctl", "enable", service
                ], check=True)
            except subprocess.CalledProcessError:
                print(f"Warning: Could not enable {service}")
        
        # Ask about additional services
        print("\nAdditional services:")
        
        additional_services = inquirer.checkbox(
            message="Select additional services to enable:",
            choices=[
                Choice("sshd", "SSH Server"),
                Choice("dhcpcd", "DHCP Client"),
                Choice("avahi-daemon", "Avahi (mDNS/Zeroconf)"),
                Choice("bluetooth", "Bluetooth support"),
                Choice("cups", "Printing support (CUPS)"),
                Choice("docker", "Docker container support")
            ]
        ).execute()
        
        # Install and enable selected services
        for service in additional_services:
            try:
                # Install package if needed
                package = service
                if service == "sshd":
                    package = "openssh"
                elif service == "bluetooth":
                    package = "bluez bluez-utils"
                
                subprocess.run([
                    "arch-chroot", self.root_mount,
                    "pacman", "-S", "--noconfirm", package
                ], check=True)
                
                # Enable service
                subprocess.run([
                    "arch-chroot", self.root_mount,
                    "systemctl", "enable", service
                ], check=True)
                
                print(f"Enabled {service} service.")
                
            except subprocess.CalledProcessError as e:
                print(f"Warning: Error enabling {service}: {e}")
        
        print("Services configured successfully.")
    
    def set_root_mount(self, root_mount):
        """Set the root mount point"""
        self.root_mount = root_mount 