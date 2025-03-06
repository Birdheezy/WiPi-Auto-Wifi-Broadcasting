# WiPi - Auto WiFi Broadcasting

A lightweight, reliable solution for automatically creating a WiFi access point on your Raspberry Pi when it's not connected to a known network.

## Overview

WiPi solves a common problem with Raspberry Pi projects: how to access your Pi when it's not connected to a known WiFi network. This can happen when:

- You take your Pi to a new location without a known WiFi network
- Your home WiFi network changes or is temporarily unavailable
- You're developing a portable project that needs to work anywhere

WiPi monitors your WiFi connection and automatically switches to Access Point mode when no known networks are available, allowing you to connect directly to your Pi. When a known network becomes available again, it switches back to client mode.

## Features

- **Automatic Mode Switching**: Seamlessly switches between client and AP modes
- **Easy Configuration**: Simple JSON configuration file
- **Systemd Integration**: Runs as a system service with automatic startup
- **Command-Line Interface**: Control and monitor from the terminal
- **Customizable**: Configure SSID, password, IP address, and more
- **Lightweight**: Minimal resource usage
- **Reliable**: Designed for headless operation

## Requirements

- Raspberry Pi with built-in WiFi (Pi Zero W, Pi 3, Pi 4, etc.)
- Raspberry Pi OS Bookworm (or newer) with NetworkManager
- Python 3.5+

## Installation

### Quick Install with Virtual Environment (Recommended)

On newer Raspberry Pi OS versions (Bookworm and later), system-wide pip installations are restricted. It's recommended to use a virtual environment:

1. Download the installation files:
   ```bash
   git clone https://github.com/Birdheezy/WiPi-Auto-Wifi-Broadcasting.git
   cd WiPi-Auto-Wifi-Broadcasting
   ```

2. If you already have a virtual environment:
   ```bash
   # Specify your virtual environment path with the --venv flag
   sudo bash install.sh --venv /path/to/your-venv
   
   # For example, if your venv is at /home/pi/metar:
   sudo bash install.sh --venv /home/pi/metar
   ```

3. If you don't have a virtual environment yet:
   ```bash
   # Create a virtual environment
   python3 -m venv ~/wipi-venv
   
   # Activate it
   source ~/wipi-venv/bin/activate
   
   # Install with the virtual environment
   sudo bash install.sh --venv ~/wipi-venv
   ```

4. Follow the prompts to configure your access point settings.

### Standard Installation (Legacy OS Versions)

For older Raspberry Pi OS versions without pip restrictions:

1. Download the installation files:
   ```bash
   git clone https://github.com/Birdheezy/WiPi-Auto-Wifi-Broadcasting.git
   cd WiPi-Auto-Wifi-Broadcasting
   ```

2. Run the installer:
   ```bash
   sudo bash install.sh
   ```

3. Follow the prompts to configure your access point settings.

### Manual Installation

If you prefer to install manually:

1. Install dependencies:
   ```bash
   sudo apt update
   sudo apt install -y network-manager python3-pip
   ```

2. Copy files to appropriate locations:
   ```bash
   sudo mkdir -p /etc/wipi
   sudo cp wipi.py /usr/local/bin/
   sudo cp wipi_service.py /usr/local/bin/
   sudo cp config.json /etc/wipi/
   sudo chmod +x /usr/local/bin/wipi.py
   sudo chmod +x /usr/local/bin/wipi_service.py
   ```

3. Install as a service:
   ```bash
   sudo python3 /usr/local/bin/wipi_service.py --install
   ```

## Usage

### Basic Commands

After installation, you can use the following commands:

- **Check Status**: `wipi-status`
- **Start Service**: `wipi-start`
- **Stop Service**: `wipi-stop`
- **Restart Service**: `wipi-restart`
- **View Logs**: `wipi-log`
- **Edit Configuration**: `wipi-config`

### Connecting to the Access Point

When your Pi can't connect to a known WiFi network, it will create an access point with:

- **SSID**: The name you configured (default: METAR-Pi)
- **Password**: The password you configured (default: METAR-Pi)
- **IP Address**: The IP address you configured (default: 192.168.8.1)

Connect to this network from your computer or mobile device, then access your Pi at the configured IP address:

- **SSH**: `ssh pi@192.168.8.1`
- **Web Interface**: `http://192.168.8.1`

### Advanced Usage

#### Force AP Mode

To force AP mode regardless of WiFi connectivity:

```bash
sudo wipi --force-ap
```

#### Check Current Status

To display detailed status information:

```bash
sudo wipi --status
```

#### Debug Mode

To enable verbose logging:

```bash
sudo wipi --debug
```

## Configuration

The configuration file is located at `/etc/wipi/config.json`. You can edit it directly or use the `wipi-config` command.

### Configuration Options

```json
{
    "ap_ssid": "METAR-Pi",           // Access point name
    "ap_password": "METAR-Pi",       // Access point password
    "ap_ip_address": "192.168.8.1",  // IP address for the access point
    "check_interval": 120,           // How often to check connectivity (seconds)
    "force_ap_mode": false,          // Force AP mode regardless of connectivity
    "debug_mode": false,             // Enable verbose logging
    "ap_channel": 6,                 // WiFi channel for the access point
    "ap_band": "bg",                 // WiFi band (bg = 2.4GHz)
    "ap_hidden": false,              // Whether to hide the SSID
    "reconnect_attempts": 3,         // Number of reconnection attempts
    "reconnect_delay": 5,            // Delay between reconnection attempts (seconds)
    "preferred_networks": [],        // List of preferred networks to connect to
    "prioritize_clients": true       // Don't disconnect clients when a known network is found
}
```

## Integration with METARMap

WiPi was originally developed for the [METARMap project](https://github.com/Birdheezy/METARMap2.0) to provide reliable access to the Pi when setting up the map in new locations. It's particularly useful for projects that need to be accessible during initial setup or when troubleshooting.

## Uninstallation

To uninstall WiPi:

```bash
sudo bash install.sh --uninstall
```

## Troubleshooting

### Installation Issues

If you encounter errors about "externally-managed-environment" during installation:
```
error: externally-managed-environment
× This environment is externally managed
```

This is due to restrictions in newer Raspberry Pi OS versions. Use the virtual environment installation method:
```bash
sudo bash install.sh --venv /path/to/your/venv
```

### Line Ending Issues

If you encounter errors like these when running the installation script:
```
install.sh: line 6: $'\r': command not found
install.sh: line 18: syntax error near unexpected token `$'{\r''
```

This is due to Windows-style line endings (CRLF) in the script. CD to the directory containing install.sh and run:
```bash
# Fix line endings in the installation script
sed -i 's/\r$//' install.sh

# Then run the installer
sudo bash install.sh --venv /path/to/your/venv
```

This commonly happens when files are edited on Windows or copied from Windows systems to the Raspberry Pi.

### Service Won't Start

Check the service status:
```bash
systemctl status wipi.service
```

View the logs:
```bash
journalctl -u wipi.service
```

### Access Point Not Created

Make sure NetworkManager is installed and running:
```bash
systemctl status NetworkManager
```

Check if your WiFi adapter supports AP mode:
```bash
iw list | grep "Supported interface modes" -A 8
```

### Can't Connect to Access Point

Verify the access point is active:
```bash
sudo wipi --status
```

Check for conflicting WiFi services:
```bash
systemctl status hostapd
systemctl status dnsmasq
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the [RaspberryConnect AccessPopup](https://www.raspberryconnect.com/projects/65-raspberrypi-hotspot-accesspoints/203-automated-switching-accesspoint-wifi-network) project
- Developed for the [METARMap project](https://github.com/Birdheezy/METARMap2.0)
