#!/usr/bin/env python3
"""
WiPi - Automatic WiFi/AP Mode Switching
Monitors WiFi connectivity and switches to AP mode when no known networks are available.
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('wipi')

# Default configuration
AP_SSID = "WiPi"
AP_PASSWORD = "raspberry"
AP_IP_ADDRESS = "192.168.8.1"

# Time intervals (in seconds)
CHECK_INTERVAL = 30        # How often to scan for known networks
WIFI_WAIT = 2             # Wait time after WiFi operations
COMMAND_TIMEOUT = 10      # Default timeout for commands

class WiPi:
    def __init__(self):
        """Initialize WiPi."""
        self.running = True
        self.ap_active = False
        self.current_wifi = None
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        # Check if NetworkManager is available
        self.check_dependencies()
        logger.info(f"WiPi initialized with SSID: {AP_SSID}")

    def check_dependencies(self):
        """Check if required dependencies are installed."""
        try:
            subprocess.run(["nmcli", "--version"], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("NetworkManager (nmcli) is not installed")
            sys.exit(1)

    def handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.ap_active:
            self.deactivate_ap()
        sys.exit(0)

    def is_wifi_connected(self) -> bool:
        """Check if connected to a WiFi network."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,STATE", "device"],
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            for line in result.stdout.splitlines():
                if line.startswith("wifi:connected"):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking WiFi connection: {e}")
            return False

    def get_saved_networks(self) -> List[str]:
        """Get list of saved WiFi networks."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
                capture_output=True,
                text=True,
                check=False
            )
            
            networks = []
            for line in result.stdout.splitlines():
                if ":802-11-wireless" in line and not line.startswith("Hotspot"):
                    networks.append(line.split(":")[0])
            return networks
        except Exception as e:
            logger.error(f"Error getting saved networks: {e}")
            return []

    def scan_for_known_networks(self) -> List[str]:
        """Scan for available known networks."""
        try:
            # Get saved networks
            saved_networks = self.get_saved_networks()
            if not saved_networks:
                logger.warning("No saved networks found")
                return []

            # Scan for networks
            subprocess.run(["nmcli", "device", "wifi", "rescan"], check=False)
            time.sleep(WIFI_WAIT)
            
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                check=False
            )
            
            available = []
            for network in saved_networks:
                if network in result.stdout:
                    available.append(network)
            
            return available
        except Exception as e:
            logger.error(f"Error scanning for networks: {e}")
            return []

    def connect_to_wifi(self, ssid: str) -> bool:
        """Connect to a specific WiFi network."""
        try:
            logger.info(f"Connecting to {ssid}")
            result = subprocess.run(
                ["nmcli", "connection", "up", ssid],
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to connect to {ssid}: {result.stderr}")
                return False
                
            time.sleep(WIFI_WAIT)
            return self.is_wifi_connected()
        except Exception as e:
            logger.error(f"Error connecting to {ssid}: {e}")
            return False

    def activate_ap(self) -> bool:
        """Activate AP mode."""
        if self.ap_active:
            return True
            
        try:
            logger.info("Activating AP mode")
            result = subprocess.run(
                ["nmcli", "device", "wifi", "hotspot",
                 "ifname", "wlan0",
                 "ssid", AP_SSID,
                 "password", AP_PASSWORD],
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to activate AP: {result.stderr}")
                return False
                
            self.ap_active = True
            return True
        except Exception as e:
            logger.error(f"Error activating AP: {e}")
            return False

    def deactivate_ap(self) -> bool:
        """Deactivate AP mode."""
        if not self.ap_active:
            return True
            
        try:
            logger.info("Deactivating AP mode")
            result = subprocess.run(
                ["nmcli", "connection", "down", f"Hotspot-{AP_SSID}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            self.ap_active = False
            return True
        except Exception as e:
            logger.error(f"Error deactivating AP: {e}")
            return False

    def run(self):
        """Main execution loop."""
        logger.info("Starting WiPi service")
        
        while self.running:
            try:
                # Check if we're connected to WiFi
                if self.is_wifi_connected():
                    if self.ap_active:
                        logger.info("WiFi connected, deactivating AP")
                        self.deactivate_ap()
                else:
                    # Look for known networks
                    networks = self.scan_for_known_networks()
                    if networks:
                        logger.info(f"Found known networks: {networks}")
                        if self.connect_to_wifi(networks[0]):
                            logger.info("Successfully connected to WiFi")
                            continue
                    
                    # If we couldn't connect, activate AP
                    if not self.ap_active:
                        logger.info("No WiFi connection, activating AP")
                        self.activate_ap()
                
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(CHECK_INTERVAL)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="WiPi - Automatic WiFi/AP Mode Switching")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    args = parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    wipi = WiPi()
    wipi.run()

if __name__ == "__main__":
    main()

