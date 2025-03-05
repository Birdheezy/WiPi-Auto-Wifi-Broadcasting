#!/usr/bin/env python3
"""
WiPi - Auto WiFi Broadcasting
A utility to automatically create a WiFi access point when not connected to a known network.
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import signal
import socket
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/wipi.log', mode='a')
    ]
)
logger = logging.getLogger('wipi')

# Default configuration
DEFAULT_CONFIG = {
    "ap_ssid": "WiPi-AP",
    "ap_password": "raspberry",
    "ap_ip_address": "192.168.4.1",
    "check_interval": 120,  # seconds
    "force_ap_mode": False,
    "debug_mode": False
}

class WiPi:
    def __init__(self, config_path="/etc/wipi/config.json"):
        """Initialize WiPi with configuration."""
        self.config_path = config_path
        self.config = self._load_config()
        self.running = True
        self.ap_active = False
        
        # Set debug mode if configured
        if self.config.get("debug_mode", False):
            logger.setLevel(logging.DEBUG)
            
        logger.info("WiPi initialized with configuration: %s", self.config)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle termination signals."""
        logger.info("Received signal %s, shutting down...", sig)
        self.running = False

    def _load_config(self):
        """Load configuration from file or use defaults."""
        config = DEFAULT_CONFIG.copy()
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                    config.update(user_config)
                    logger.debug("Loaded configuration from %s", self.config_path)
            else:
                logger.warning("Configuration file not found at %s, using defaults", self.config_path)
                # Create config directory if it doesn't exist
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                # Save default config
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                    logger.info("Created default configuration at %s", self.config_path)
        except Exception as e:
            logger.error("Error loading configuration: %s", e)
        return config

    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
                logger.debug("Saved configuration to %s", self.config_path)
        except Exception as e:
            logger.error("Error saving configuration: %s", e)

    def is_connected_to_wifi(self):
        """Check if connected to a known WiFi network."""
        try:
            # Check if wlan0 has an IP address
            result = subprocess.run(
                ["ip", "-4", "addr", "show", "wlan0"],
                capture_output=True, text=True, check=False
            )
            
            if "inet" in result.stdout:
                # Check if we're in client mode (not AP mode)
                mode_result = subprocess.run(
                    ["iwconfig", "wlan0"], 
                    capture_output=True, text=True, check=False
                )
                if "Mode:Master" not in mode_result.stdout:
                    logger.debug("Connected to WiFi in client mode")
                    return True
            
            logger.debug("Not connected to WiFi in client mode")
            return False
        except Exception as e:
            logger.error("Error checking WiFi connection: %s", e)
            return False

    def get_known_networks(self):
        """Get list of known WiFi networks."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME", "connection", "show"],
                capture_output=True, text=True, check=False
            )
            networks = [line for line in result.stdout.strip().split('\n') if line]
            logger.debug("Found known networks: %s", networks)
            return networks
        except Exception as e:
            logger.error("Error getting known networks: %s", e)
            return []

    def scan_for_known_networks(self):
        """Scan for available known WiFi networks."""
        try:
            # Get list of known networks
            known_networks = self.get_known_networks()
            
            # Scan for available networks
            subprocess.run(["nmcli", "device", "wifi", "rescan"], check=False)
            time.sleep(2)  # Give time for scan to complete
            
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list"],
                capture_output=True, text=True, check=False
            )
            available_networks = [line for line in result.stdout.strip().split('\n') if line]
            
            # Find intersection of known and available networks
            available_known = [net for net in known_networks if net in available_networks]
            logger.debug("Available known networks: %s", available_known)
            
            return available_known
        except Exception as e:
            logger.error("Error scanning for networks: %s", e)
            return []

    def connect_to_wifi(self, network_name):
        """Connect to a specific WiFi network."""
        try:
            # Deactivate AP mode if active
            if self.ap_active:
                self.deactivate_ap()
            
            logger.info("Attempting to connect to network: %s", network_name)
            result = subprocess.run(
                ["nmcli", "connection", "up", network_name],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                logger.info("Successfully connected to %s", network_name)
                return True
            else:
                logger.error("Failed to connect to %s: %s", network_name, result.stderr)
                return False
        except Exception as e:
            logger.error("Error connecting to WiFi: %s", e)
            return False

    def activate_ap(self):
        """Activate access point mode."""
        if self.ap_active:
            logger.debug("AP already active")
            return True
            
        try:
            logger.info("Activating access point mode")
            
            # Check if AP connection exists
            ap_exists = subprocess.run(
                ["nmcli", "connection", "show", self.config["ap_ssid"]],
                capture_output=True, text=True, check=False
            ).returncode == 0
            
            if not ap_exists:
                # Create AP connection
                logger.info("Creating AP connection: %s", self.config["ap_ssid"])
                create_result = subprocess.run([
                    "nmcli", "device", "wifi", "hotspot", 
                    "ifname", "wlan0", 
                    "ssid", self.config["ap_ssid"], 
                    "password", self.config["ap_password"]
                ], capture_output=True, text=True, check=False)
                
                if create_result.returncode != 0:
                    logger.error("Failed to create AP: %s", create_result.stderr)
                    return False
            else:
                # Activate existing AP connection
                activate_result = subprocess.run([
                    "nmcli", "connection", "up", self.config["ap_ssid"]
                ], capture_output=True, text=True, check=False)
                
                if activate_result.returncode != 0:
                    logger.error("Failed to activate AP: %s", activate_result.stderr)
                    return False
            
            # Set AP IP address
            ip_result = subprocess.run([
                "sudo", "ip", "addr", "add", 
                f"{self.config['ap_ip_address']}/24", 
                "dev", "wlan0"
            ], capture_output=True, text=True, check=False)
            
            if ip_result.returncode != 0 and "File exists" not in ip_result.stderr:
                logger.warning("Failed to set AP IP address: %s", ip_result.stderr)
            
            self.ap_active = True
            logger.info("Access point activated: %s", self.config["ap_ssid"])
            return True
            
        except Exception as e:
            logger.error("Error activating AP: %s", e)
            return False

    def deactivate_ap(self):
        """Deactivate access point mode."""
        if not self.ap_active:
            logger.debug("AP already inactive")
            return True
            
        try:
            logger.info("Deactivating access point mode")
            
            # Down the AP connection
            result = subprocess.run([
                "nmcli", "connection", "down", self.config["ap_ssid"]
            ], capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                logger.warning("Failed to deactivate AP: %s", result.stderr)
            
            self.ap_active = False
            logger.info("Access point deactivated")
            return True
            
        except Exception as e:
            logger.error("Error deactivating AP: %s", e)
            return False

    def get_ip_addresses(self):
        """Get all IP addresses of the device."""
        try:
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True, text=True, check=False
            )
            ips = result.stdout.strip().split()
            logger.debug("IP addresses: %s", ips)
            return ips
        except Exception as e:
            logger.error("Error getting IP addresses: %s", e)
            return []

    def get_hostname(self):
        """Get the hostname of the device."""
        try:
            result = subprocess.run(
                ["hostname"],
                capture_output=True, text=True, check=False
            )
            hostname = result.stdout.strip()
            logger.debug("Hostname: %s", hostname)
            return hostname
        except Exception as e:
            logger.error("Error getting hostname: %s", e)
            return "unknown"

    def display_status(self):
        """Display current status information."""
        status = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hostname": self.get_hostname(),
            "ip_addresses": self.get_ip_addresses(),
            "ap_active": self.ap_active,
            "ap_ssid": self.config["ap_ssid"],
            "ap_ip": self.config["ap_ip_address"],
            "wifi_connected": self.is_connected_to_wifi(),
            "known_networks": self.get_known_networks()
        }
        
        logger.info("Status: %s", status)
        return status

    def run(self):
        """Main execution loop."""
        logger.info("Starting WiPi service")
        
        while self.running:
            try:
                # Check if we should force AP mode
                if self.config.get("force_ap_mode", False):
                    logger.info("Forcing AP mode as configured")
                    self.activate_ap()
                # Otherwise check connectivity and switch modes as needed
                elif not self.is_connected_to_wifi():
                    logger.info("Not connected to WiFi, checking for known networks")
                    available_networks = self.scan_for_known_networks()
                    
                    if available_networks:
                        # Try to connect to the first available known network
                        self.connect_to_wifi(available_networks[0])
                    else:
                        # No known networks available, activate AP
                        logger.info("No known networks available, activating AP")
                        self.activate_ap()
                elif self.ap_active:
                    # Connected to WiFi but AP is active, deactivate AP
                    logger.info("Connected to WiFi, deactivating AP")
                    self.deactivate_ap()
                else:
                    # Already connected to WiFi and AP is inactive
                    logger.debug("Connected to WiFi, no action needed")
                
                # Display current status
                self.display_status()
                
                # Sleep for the configured interval
                logger.debug("Sleeping for %s seconds", self.config["check_interval"])
                for _ in range(int(self.config["check_interval"])):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error("Error in main loop: %s", e)
                time.sleep(10)  # Sleep briefly before retrying

        logger.info("WiPi service stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="WiPi - Auto WiFi Broadcasting")
    parser.add_argument("-c", "--config", default="/etc/wipi/config.json", help="Path to configuration file")
    parser.add_argument("-f", "--force-ap", action="store_true", help="Force AP mode")
    parser.add_argument("-s", "--status", action="store_true", help="Display status and exit")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Initialize WiPi
    wipi = WiPi(config_path=args.config)
    
    # Override config with command line arguments
    if args.force_ap:
        wipi.config["force_ap_mode"] = True
    if args.debug:
        wipi.config["debug_mode"] = True
        logger.setLevel(logging.DEBUG)
    
    # Just display status if requested
    if args.status:
        wipi.display_status()
        return
    
    # Run the main loop
    wipi.run()


if __name__ == "__main__":
    main()
