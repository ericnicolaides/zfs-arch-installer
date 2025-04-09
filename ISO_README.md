# Arch Linux LTS with ZFS ISO

This ISO includes:
- Arch Linux with LTS kernel
- OpenZFS pre-installed and configured
- Standard Arch Installer (archinstall)
- ZFS Arch Installer (specialized for ZFS installations)

## Using the ZFS Arch Installer

The ZFS Arch Installer provides a streamlined process for installing Arch Linux with ZFS as the root filesystem. It handles:

- Disk partitioning with proper ZFS support
- Various ZFS pool configurations (single, mirror, RAIDZ1/2) 
- ZFS native encryption
- Boot options (GRUB or systemd-boot)
- Complete system configuration

### To use the ZFS Arch Installer:

1. Boot from this ISO
2. Ensure you're connected to the internet
3. Run the installer:
   ```
   cd /root/zfs-arch-installer
   sudo python arch_zfs_installer/main.py
   ```
4. Follow the interactive prompts to complete your installation

## Using Standard Arch Install

If you prefer to use the regular archinstall tool, simply type:
```
archinstall
```

## Manual ZFS Installation

You can also perform a manual ZFS installation using the ZFS tools provided:
- `zpool` - ZFS pool management
- `zfs` - ZFS dataset management
- All standard ZFS utilities are pre-installed

## Requirements

- UEFI system (BIOS not supported for ZFS boot)
- At least 4GB RAM
- Internet connection for package installation 