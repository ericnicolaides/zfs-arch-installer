# Arch Linux ZFS Installer

A specialized installer for setting up Arch Linux with ZFS as the root filesystem. This tool provides a streamlined, interactive installation process that handles all the complexities of ZFS configuration while maintaining the flexibility and power of Arch Linux.

## Features

- Interactive disk selection and partitioning
- ZFS pool configuration with support for:
  - Single disk
  - Mirror
  - RAIDZ1/2
- ZFS native encryption support
- Bootloader configuration (GRUB or systemd-boot)
- Automatic system configuration
- UEFI support
- Debug mode for troubleshooting

## Requirements

- UEFI system (BIOS not supported for ZFS boot)
- At least 4GB RAM
- Internet connection for package installation
- Root privileges

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ericnicolaides/Arch_ZFS_Installer.git
   cd Arch_ZFS_Installer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the installer:
   ```bash
   sudo python arch_zfs_installer/main.py
   ```

## Usage

The installer provides an interactive interface that guides you through the installation process:

1. Disk selection and partitioning
2. ZFS pool and dataset setup
3. Boot configuration
4. System installation
5. System configuration
6. Bootloader installation

For debugging purposes, you can run the installer with the `--debug` flag:
```bash
sudo python arch_zfs_installer/main.py --debug
```

## Project Structure

```
arch_zfs_installer/
├── config/          # Configuration files
├── utils/           # Utility modules
│   ├── disk_manager.py
│   ├── zfs_manager.py
│   ├── boot_manager.py
│   ├── system_config.py
│   └── installer.py
├── main.py          # Main entry point
└── __init__.py      # Package initialization
```

## Warning

⚠️ This installer will modify your system. Make sure you have a backup of all important data before proceeding.

## License

This project is licensed under the terms specified in the LICENSE file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions, please open an issue in the GitHub repository. 