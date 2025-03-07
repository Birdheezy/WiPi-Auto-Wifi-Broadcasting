#!/usr/bin/env python3
"""
WiPi - Auto WiFi Broadcasting
A utility to automatically create a WiFi access point when not connected to a known network.
"""

import os
import sys
import time
import logging
import argparse
import subprocess
import signal
import socket
from datetime import datetime
import re

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

# Hardcoded settings (these will be modified by the installer/settings editor)
AP_SSID = "METAR-Pi"
AP_PASSWORD = "METAR-Pi"
AP_IP_ADDRESS = "192.168.8.1"
CHECK_INTERVAL = 120
FORCE_AP_MODE = False
DEBUG_MODE = False
AP_CHANNEL = 6
AP_BAND = "bg"
AP_HIDDEN = False
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5
PRIORITIZE_CLIENTS = True
AP_OPEN = False

class WiPi:
    def __init__(self):
        """Initialize WiPi with hardcoded settings."""
        self.running = True
        self.ap_active = False
        
        # Set debug mode if configured
        if DEBUG_MODE:
            logger.setLevel(logging.DEBUG)
            
        logger.info("WiPi initialized with settings: SSID=%s, IP=%s", AP_SSID, AP_IP_ADDRESS)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle termination signals."""
        logger.info("Received signal %s, shutting down...", sig)
        self.running = False

    def is_connected_to_wifi(self):
        """Check if connected to a WiFi network."""
        try:
            # Find the wireless interface
            interfaces = subprocess.check_output(["ip", "link"]).decode()
            match = re.search(r"wlan[0-9]+: <BROADCAST,MULTICAST,UP,LOWER_UP>\s*.*", interfaces)
            if not match:
                return False  # No wireless interface found
            interface = match.group(0).split(":")[0]

            result = subprocess.run(
                ["ip", "-4", "addr", "show", interface],
                capture_output=True, text=True, check=True
            )
            
            # Check if there is an ip address, if there is it should be connected
            if "inet " in result.stdout:
                return True
            else:
                return False
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking WiFi connection: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error checking WiFi connection: {e}")
            return False

    def has_connected_clients(self):
        """Check if there are clients connected to the access point."""
        if not self.ap_active:
            return False
            
        try:
            # Method 1: Check using NetworkManager connection info
            result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device", "status"],
                capture_output=True, text=True, check=False
            )
            
            # Check if wlan0 is in AP mode
            ap_mode = False
            for line in result.stdout.strip().split('\n'):
                if 'wlan0:' in line and AP_SSID in line:
                    ap_mode = True
                    break
                    
            if not ap_mode:
                return False
                
            # Method 2: Check ARP table for clients
            arp_result = subprocess.run(
                ["arp", "-n"],
                capture_output=True, text=True, check=False
            )
            
            # Parse ARP table to find clients on the AP's subnet
            ap_ip_prefix = '.'.join(AP_IP_ADDRESS.split('.')[:3])
            client_count = 0
            
            for line in arp_result.stdout.strip().split('\n')[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 3:
                    ip = parts[0]
                    if ip.startswith(ap_ip_prefix) and ip != AP_IP_ADDRESS:
                        client_count += 1
                        logger.debug(f"Found client with IP: {ip}")
            
            # Method 3: As a fallback, check if there are any DHCP leases
            # This assumes the standard location for dnsmasq leases file
            leases_file = "/var/lib/misc/dnsmasq.leases"
            if os.path.exists(leases_file):
                with open(leases_file, 'r') as f:
                    leases = f.readlines()
                    for lease in leases:
                        if ap_ip_prefix in lease:
                            client_count += 1
                            logger.debug(f"Found DHCP lease: {lease.strip()}")
            
            logger.debug(f"Detected {client_count} connected clients")
            return client_count > 0
            
        except Exception as e:
            logger.error(f"Error checking for connected clients: {e}")
            # If we can't determine, assume no clients to be safe
            return False

    def get_known_networks(self):
        """Get the list of known WiFi networks."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME", "connection", "show"],
                capture_output=True, text=True, check=False
            )
            networks = [line for line in result.stdout.strip().split('\n') if line]
            logger.debug("Known networks: %s", networks)
            return networks
        except Exception as e:
            logger.error("Error getting known networks: %s", e)
            return []
        
    def scan_for_known_networks(self):
        """Scan for available known WiFi networks."""
        try:
            # Get list of known networks
            known_networks = self.get_known_networks()
            
            # Force a rescan by turning WiFi off and on
            logger.debug("Forcing WiFi rescan...")
            try:
                subprocess.run(["nmcli", "radio", "wifi", "off"], check=False)
                time.sleep(1)
                subprocess.run(["nmcli", "radio", "wifi", "on"], check=False)
                time.sleep(2)  # Give time for interface to come up
            except Exception as e:
                logger.warning(f"Error cycling WiFi: {e}")
            
            # Request a scan
            try:
                subprocess.run(["nmcli", "device", "wifi", "rescan"], check=False)
            except Exception as e:
                logger.warning(f"Error initiating rescan: {e}")
            
            # Give more time for scan to complete
            time.sleep(5)
            
            # Try multiple times to get scan results
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    result = subprocess.run(
                        ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list"],
                        capture_output=True, text=True, check=False
                    )
                    available_networks = [line for line in result.stdout.strip().split('\n') if line]
                    
                    if available_networks:
                        # Find intersection of known and available networks
                        available_known = [net for net in known_networks if net in available_networks]
                        logger.debug(f"Available known networks (attempt {attempt + 1}): {available_known}")
                        
                        if available_known:
                            return available_known
                except Exception as e:
                    logger.warning(f"Error getting scan results (attempt {attempt + 1}): {e}")
                
                if attempt < max_attempts - 1:
                    time.sleep(2)  # Wait before next attempt
            
            logger.warning("No known networks found after multiple attempts")
            return []
            
        except Exception as e:
            logger.error(f"Error scanning for networks: {e}")
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
            
            # First, check for and delete any existing AP connections with similar names
            try:
                # Get list of all connections
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME", "connection", "show"],
                    capture_output=True, text=True, check=False
                )
                
                # Look for connections that might be related to our AP
                for conn in result.stdout.strip().split('\n'):
                    if conn and (conn == "AccessPopup" or conn == "Hotspot"):
                        logger.info(f"Removing existing connection: {conn}")
                        subprocess.run(["nmcli", "connection", "delete", conn], check=False)
            except Exception as e:
                logger.warning(f"Error cleaning up existing connections: {e}")
            
            # Create AP connection with explicit name "Hotspot"
            logger.info(f"Creating AP connection: {AP_SSID} (named 'Hotspot')")
            
            hotspot_command = [
                "nmcli", "connection", "add",
                "type", "wifi",
                "ifname", "wlan0",
                "con-name", "Hotspot",
                "autoconnect", "no",
                "ssid", AP_SSID,
                "mode", "ap"
            ]
            
            # Add security settings if ap_open is False
            if not AP_OPEN:
                hotspot_command.extend([
                    "wifi-sec.key-mgmt", "wpa-psk",
                    "wifi-sec.psk", AP_PASSWORD
                ])
            
            create_result = subprocess.run(hotspot_command, capture_output=True, text=True, check=False)
            
            if create_result.returncode != 0:
                logger.error(f"Failed to create AP connection: {create_result.stderr}")
                return False
                
            # Activate the connection
            activate_result = subprocess.run(
                ["nmcli", "connection", "up", "Hotspot"],
                capture_output=True, text=True, check=False
            )
            
            if activate_result.returncode != 0:
                logger.error(f"Failed to activate AP connection: {activate_result.stderr}")
                return False
            
            # Set AP IP address
            ip_result = subprocess.run([
                "sudo", "ip", "addr", "add", 
                f"{AP_IP_ADDRESS}/24", 
                "dev", "wlan0"
            ], capture_output=True, text=True, check=False)
            
            if ip_result.returncode != 0 and "File exists" not in ip_result.stderr:
                logger.warning(f"Failed to set AP IP address: {ip_result.stderr}")
            
            self.ap_active = True
            logger.info(f"Access point activated: {AP_SSID}")
            return True
            
        except Exception as e:
            logger.error(f"Error activating AP: {e}")
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
                "nmcli", "connection", "down", "Hotspot"
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
            "ap_ssid": AP_SSID,
            "ap_ip": AP_IP_ADDRESS,
            "wifi_connected": self.is_connected_to_wifi(),
            "known_networks": self.get_known_networks(),
            "clients_connected": self.has_connected_clients() if self.ap_active else False
        }
        
        logger.info("Status: %s", status)
        return status

    def run(self):
        """Main execution loop."""
        logger.info("Starting WiPi service")
        logger.info(f"Using SSID: {AP_SSID}")
        
        while self.running:
            try:
                # Check if we should force AP mode
                if FORCE_AP_MODE:
                    logger.info("Forcing AP mode as configured")
                    if not self.ap_active:
                        self.activate_ap()
                # Check if AP is active and has no clients
                elif self.ap_active and not self.has_connected_clients():
                    logger.info("AP is active but no clients connected, scanning for known networks")
                    available_networks = self.scan_for_known_networks()
                    
                    if available_networks:
                        # Try to connect to the first available known network
                        if self.connect_to_wifi(available_networks[0]):
                            logger.info("Successfully connected to known network")
                            self.deactivate_ap()
                        else:
                            logger.info("Failed to connect to known network, maintaining AP mode")
                    else:
                        logger.info("No known networks found, maintaining AP mode")
                # Otherwise check connectivity and switch modes as needed
                elif not self.is_connected_to_wifi():
                    logger.info("Not connected to WiFi, checking for known networks")
                    
                    # Check if clients are connected to our AP
                    if self.ap_active and self.has_connected_clients():
                        logger.info("Clients are connected to the AP, maintaining AP mode")
                        # Skip network scanning to avoid disrupting clients
                        time.sleep(CHECK_INTERVAL)
                        continue
                    
                    # If AP is not active or no clients are connected, scan for networks
                    available_networks = self.scan_for_known_networks()
                    
                    if not available_networks:
                        logger.info("No known networks available, activating/maintaining AP mode")
                        if not self.ap_active:
                            self.activate_ap()
                    else:
                        # Try to connect to the first available known network
                        if self.connect_to_wifi(available_networks[0]):
                            if self.ap_active:
                                self.deactivate_ap()
                        else:
                            # Connection failed, ensure AP is active
                            logger.info("Failed to connect to known network, activating/maintaining AP mode")
                            if not self.ap_active:
                                self.activate_ap()
                elif self.ap_active:
                    # Connected to WiFi but AP is active
                    if self.has_connected_clients():
                        logger.info("Connected to WiFi but clients are using the AP, maintaining AP mode")
                    else:
                        # No clients connected, safe to deactivate AP
                        logger.info("Connected to WiFi and no clients on AP, deactivating AP")
                        self.deactivate_ap()
                else:
                    # Already connected to WiFi and AP is inactive
                    logger.debug("Connected to WiFi, no action needed")
                
                # Display current status
                self.display_status()
                
                # Sleep for the configured interval
                logger.debug("Sleeping for %s seconds", CHECK_INTERVAL)
                for _ in range(int(CHECK_INTERVAL)):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error("Error in main loop: %s", e)
                # If we hit an error, make sure AP is active as a fallback
                if not self.ap_active:
                    logger.info("Error occurred, ensuring AP is active as fallback")
                    self.activate_ap()
                time.sleep(10)  # Brief sleep before retrying

        logger.info("WiPi service stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="WiPi - Auto WiFi Broadcasting")
    parser.add_argument("-f", "--force-ap", action="store_true", help="Force AP mode")
    parser.add_argument("-s", "--status", action="store_true", help="Display status and exit")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-o", "--open-ap", action="store_true", help="Create an open (no password) access point")
    parser.add_argument("-p", "--prioritize-clients", action="store_true", help="Prioritize client connections over WiFi connectivity")
    args = parser.parse_args()
    
    # Initialize WiPi
    wipi = WiPi()
    
    # Override settings with command line arguments
    global FORCE_AP_MODE, DEBUG_MODE, AP_OPEN, PRIORITIZE_CLIENTS
    
    if args.force_ap:
        FORCE_AP_MODE = True
    if args.debug:
        DEBUG_MODE = True
        logger.setLevel(logging.DEBUG)
    if args.open_ap:
        AP_OPEN = True
    if args.prioritize_clients:
        PRIORITIZE_CLIENTS = True
    
    # Just display status if requested
    if args.status:
        wipi.display_status()
        return
    
    # Run the main loop
    wipi.run()


if __name__ == "__main__":
    main()
