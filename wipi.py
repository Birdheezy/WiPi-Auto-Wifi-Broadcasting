#!/usr/bin/env python3
"""
WiPi - Automatic WiFi/AP Mode Switching

This script monitors WiFi connectivity and automatically switches to AP mode
when no known networks are available. It uses NetworkManager for all network operations.
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
import re
from typing import List, Dict, Optional, Tuple, Any

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
CHECK_INTERVAL = 30           # How often to scan for known networks
MAIN_LOOP_INTERVAL = 15        # Sleep time between main loop iterations
FORCE_AP_SLEEP_INTERVAL = 30  # Sleep time when in forced AP mode
ERROR_SLEEP_INTERVAL = 5      # Sleep time after an error
WIFI_OFF_WAIT = 2             # Wait time after turning WiFi off
WIFI_ON_WAIT = 2              # Wait time after turning WiFi on
AP_ACTIVATION_WAIT = 2        # Wait time after activating AP mode
SCAN_RETRY_WAIT = 2           # Wait time between network scan attempts
DISCONNECT_COUNT_THRESHOLD = 2 # Number of consecutive disconnections before activating AP
DISCONNECT_TIME_THRESHOLD = 30 # Time since last connection before activating AP
INTERFACE_RESTART_THRESHOLD = 12 # Number of consecutive failures before restarting interface
COMMAND_TIMEOUT = 5           # Default timeout for commands
AP_COMMAND_TIMEOUT = 10       # Timeout for AP activation commands
PING_TIMEOUT = 3              # Timeout for ping commands
ROUTE_CHECK_TIMEOUT = 2       # Timeout for route check commands

# Other configuration
FORCE_AP_MODE = False
OPEN_AP = False
PRIORITIZE_CLIENTS = False

# Default installation directory
INSTALL_DIR = '/home/pi/wipi'

class WiPi:
    """Main WiPi class that handles WiFi monitoring and AP mode switching."""
    
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
        
        # Initialize status
        self.update_status()
        
        # Restart NetworkManager on startup - Changed from settings.service
        logger.info("Restarting NetworkManager during WiPi startup")
        try:
            subprocess.run(
                ["sudo", "systemctl", "restart", "NetworkManager"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=AP_COMMAND_TIMEOUT
            )
            logger.info("Successfully restarted NetworkManager")
        except Exception as e:
            logger.error(f"Failed to restart NetworkManager: {e}")
        
        logger.info(f"WiPi initialized with SSID: {AP_SSID}, Password: {'<hidden>' if not OPEN_AP else 'None (Open)'}")
        
    def check_dependencies(self):
        """Check if required dependencies are installed."""
        try:
            result = subprocess.run(["nmcli", "--version"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          text=True,
                          check=True)
            logger.debug(f"NetworkManager version: {result.stdout.strip()}")
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("NetworkManager (nmcli) is not installed or not in PATH")
            logger.error("Please install NetworkManager: sudo apt install network-manager")
            sys.exit(1)
            
        # Check if NetworkManager is running
        try:
            result = subprocess.run(["systemctl", "is-active", "NetworkManager"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          text=True,
                          check=False)
            if result.stdout.strip() != "active":
                logger.error("NetworkManager service is not running")
                logger.error("Please start NetworkManager: sudo systemctl start NetworkManager")
                sys.exit(1)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("Could not check if NetworkManager is running")
    
    def handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.ap_active:
            self.deactivate_ap()
            
        # Restart NetworkManager on shutdown - Changed from settings.service
        logger.info("Restarting NetworkManager during WiPi shutdown")
        try:
            subprocess.run(
                ["sudo", "systemctl", "restart", "NetworkManager"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=AP_COMMAND_TIMEOUT
            )
            logger.info("Successfully restarted NetworkManager")
        except Exception as e:
            logger.error(f"Failed to restart NetworkManager: {e}")
            
        sys.exit(0)
    
    def update_status(self):
        """Update current WiFi and AP status."""
        self.current_wifi = self.get_current_wifi()
        self.ap_active = self.is_ap_active()
    
    def get_current_wifi(self) -> Optional[str]:
        """Get the SSID of the currently connected WiFi network."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,DEVICE,TYPE,STATE", "connection", "show", "--active"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to get active connections: {result.stderr}")
                return None
            
            for line in result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 4 and parts[2] == "802-11-wireless" and parts[3] == "activated":
                    return parts[0]  # Return the connection name (SSID)
            
            return None
        except Exception as e:
            logger.error(f"Error getting current WiFi: {e}")
            return None
    
    def is_wifi_connected(self) -> bool:
        """
        Check if WiFi is actually connected by checking multiple indicators.
        This handles the case where the interface might show as DORMANT but still be connected.
        """
        try:
            # Method 1: Check if interface has an IP address (most reliable indicator)
            ip_result = subprocess.run(
                ["ip", "addr", "show", "wlan0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            has_ip = False
            if ip_result.returncode == 0:
                # Check if interface has an inet (IPv4) address
                has_ip = "inet " in ip_result.stdout
                logger.debug(f"WiFi interface has IP: {has_ip}")
                
                # If no IP, no need to check further
                if not has_ip:
                    return False
            
            # Method 2: Check NetworkManager device state
            nm_result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,STATE", "device"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            nm_connected = False
            if nm_result.returncode == 0:
                for line in nm_result.stdout.splitlines():
                    parts = line.split(':')
                    if len(parts) >= 2 and parts[0] == "wlan0":
                        if parts[1] == "connected":
                            nm_connected = True
                        logger.debug(f"NetworkManager reports wlan0 state: {parts[1]}")
            
            # Method 3: Try a basic connectivity check if we have an IP
            has_connectivity = False
            if has_ip:
                try:
                    # Try to reach a reliable host (Google DNS)
                    ping_result = subprocess.run(
                        ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=PING_TIMEOUT
                    )
                    has_connectivity = ping_result.returncode == 0
                    logger.debug(f"Connectivity check (ping): {has_connectivity}")
                except (subprocess.TimeoutExpired, Exception) as e:
                    logger.debug(f"Error in connectivity check: {e}")
                    # Fall back to checking default route
                    try:
                        route_result = subprocess.run(
                            ["ip", "route", "show", "default"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False,
                            timeout=ROUTE_CHECK_TIMEOUT
                        )
                        # If we have a default route, we're probably connected
                        has_connectivity = route_result.returncode == 0 and route_result.stdout.strip() != ""
                        logger.debug(f"Default route exists: {has_connectivity}")
                    except Exception as e:
                        logger.debug(f"Error checking default route: {e}")
            
            # Log all results for debugging
            logger.debug(f"WiFi connection check: IP={has_ip}, NM={nm_connected}, Connectivity={has_connectivity}")
            
            # Consider connected if we have an IP and either NM reports connected or we have connectivity
            # This handles the case where the interface might show as DORMANT but still be connected
            return has_ip and (nm_connected or has_connectivity)
            
        except Exception as e:
            logger.error(f"Error checking WiFi connection: {e}")
            return False
    
    def is_connected_to_wifi(self) -> bool:
        """Check if connected to a WiFi network."""
        # First check if we have an active connection
        has_connection = self.get_current_wifi() is not None
        
        # Then verify the actual device state
        is_connected = self.is_wifi_connected()
        
        if has_connection and not is_connected:
            logger.warning("NetworkManager reports an active connection but device is not connected")
        
        # Return True only if both checks pass
        return has_connection and is_connected
    
    def is_ap_active(self) -> bool:
        """Check if AP mode is active."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,DEVICE,TYPE,STATE", "connection", "show", "--active"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to check AP status: {result.stderr}")
                return False
            
            # Look for a connection with the AP SSID
            conn_name = f"Hotspot-{AP_SSID}"
            for line in result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 4 and (parts[0] == conn_name or parts[0] == f"Hotspot {AP_SSID}"):
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking AP status: {e}")
            return False
    
    def has_connected_clients(self) -> bool:
        """Check if clients are connected to the AP."""
        if not self.ap_active:
            return False
            
        try:
            # Get the interface used for the AP
            ap_interface = None
            conn_name = f"Hotspot-{AP_SSID}"
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            for line in result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and (parts[0] == conn_name or parts[0] == f"Hotspot {AP_SSID}"):
                    ap_interface = parts[1]
                    break
            
            if not ap_interface:
                return False
                
            # Check for connected clients using iw
            result = subprocess.run(
                ["iw", "dev", ap_interface, "station", "dump"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # If there's any output, clients are connected
            return bool(result.stdout.strip())
            
        except Exception as e:
            logger.error(f"Error checking for connected clients: {e}")
            return False
    
    def get_saved_wifi_networks(self) -> List[str]:
        """Get a list of saved WiFi networks from NetworkManager."""
        saved_networks = []
        
        try:
            # Get list of saved connections
            saved_result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if saved_result.returncode != 0:
                logger.error(f"Failed to get saved connections: {saved_result.stderr}")
                return []
            
            # Filter for WiFi connections and exclude hotspots
            for line in saved_result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] == "802-11-wireless" and not parts[0].startswith("Hotspot"):
                    saved_networks.append(parts[0])
            
            logger.debug(f"Found {len(saved_networks)} saved WiFi networks: {', '.join(saved_networks) if saved_networks else 'None'}")
            return saved_networks
            
        except Exception as e:
            logger.error(f"Error getting saved networks: {e}")
            return []
    
    def scan_for_known_networks(self) -> List[str]:
        """
        Scan for available WiFi networks and return a list of known networks.
        Forces a rescan to ensure fresh results.
        """
        known_networks = []
        
        try:
            # Get saved networks first
            saved_networks = self.get_saved_wifi_networks()
            logger.debug(f"Found saved networks: {saved_networks}")
            
            if not saved_networks:
                logger.warning("No saved WiFi networks found in NetworkManager")
                # If no saved networks, we should activate AP mode
                if not self.ap_active:
                    logger.info("No saved networks, activating AP mode")
                    self.activate_ap()
                return []
            
            # Force a WiFi rescan by cycling the radio
            logger.debug("Forcing WiFi rescan...")
            subprocess.run(["nmcli", "radio", "wifi", "off"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=False)
            time.sleep(WIFI_OFF_WAIT)
            subprocess.run(["nmcli", "radio", "wifi", "on"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=False)
            time.sleep(WIFI_ON_WAIT)  # Wait for the interface to stabilize

            # Try up to 3 times to get scan results
            for attempt in range(3):
                # Scan for available networks
                scan_result = subprocess.run(
                    ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list", "--rescan", "yes"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if scan_result.returncode != 0:
                    logger.error(f"Failed to scan for networks: {scan_result.stderr}")
                    time.sleep(SCAN_RETRY_WAIT)
                    continue
                
                available_ssids = [line for line in scan_result.stdout.splitlines() if line]
                logger.debug(f"Found {len(available_ssids)} available networks: {available_ssids}")
                
                # Find intersection of saved and available networks
                for ssid in saved_networks:
                    if ssid in available_ssids:
                        known_networks.append(ssid)
                
                if known_networks:
                    break
                    
                logger.debug(f"No known networks found on attempt {attempt+1}, waiting...")
                time.sleep(SCAN_RETRY_WAIT)
            
            logger.info(f"Found {len(known_networks)} known networks: {', '.join(known_networks) if known_networks else 'None'}")
            
            # If no known networks found after all attempts, activate AP mode
            if not known_networks and not self.ap_active:
                logger.info("No known networks found after scanning, activating AP mode")
                self.activate_ap()
            
            return known_networks
            
        except Exception as e:
            logger.error(f"Error scanning for networks: {e}")
            # On error, activate AP mode as fallback
            if not self.ap_active:
                logger.info("Error during network scan, activating AP mode as fallback")
                self.activate_ap()
            return []
    
    def connect_to_wifi(self, ssid: str) -> bool:
        """Connect to a specific WiFi network."""
        logger.info(f"Attempting to connect to {ssid}")
        
        try:
            # Add timeout to prevent hanging
            result = subprocess.run(
                ["nmcli", "connection", "up", ssid],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT  # Add timeout constant
            )
            
            if result.returncode != 0:
                # More specific error handling
                if "auth" in result.stderr.lower():
                    logger.error(f"Authentication failed for {ssid}. Password may be incorrect.")
                elif "not found" in result.stderr.lower():
                    logger.error(f"Network {ssid} not found.")
                elif "timeout" in result.stderr.lower():
                    logger.error(f"Connection timeout while connecting to {ssid}")
                else:
                    logger.error(f"Failed to connect to {ssid}: {result.stderr}")
                return False
            
            # Add connection verification
            time.sleep(WIFI_ON_WAIT)
            if not self.is_wifi_connected():
                logger.error(f"Connected to {ssid} but no network connectivity")
                return False
            
            logger.info(f"Successfully connected to {ssid}")
            self.current_wifi = ssid
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Connection command timed out for {ssid}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to {ssid}: {e}")
            return False
    
    def activate_ap(self) -> bool:
        """Activate AP mode, reusing existing profile if available."""
        if self.ap_active:
            logger.info("AP mode already active")
            return True
        
        logger.info(f"Activating AP mode with SSID: {AP_SSID}")
        
        try:
            # Ensure WiFi is enabled without restarting NetworkManager
            subprocess.run(
                ["nmcli", "radio", "wifi", "on"],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            # Wait a moment for radio to be fully on
            time.sleep(WIFI_ON_WAIT)
            
            # Check if our hotspot profile already exists
            conn_name = f"Hotspot-{AP_SSID}"
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,UUID", "connection", "show"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            hotspot_exists = False
            hotspot_uuid = None
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split(':')
                    if len(parts) >= 2 and (parts[0] == conn_name or parts[0] == f"Hotspot {AP_SSID}"):
                        hotspot_exists = True
                        hotspot_uuid = parts[1]
                        logger.info(f"Found existing hotspot profile: {parts[0]} ({hotspot_uuid})")
                        break
            
            # If hotspot profile exists, just activate it
            if hotspot_exists and hotspot_uuid:
                logger.info(f"Activating existing hotspot profile")
                activate_result = subprocess.run(
                    ["nmcli", "connection", "up", hotspot_uuid],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=AP_COMMAND_TIMEOUT
                )
                
                if activate_result.returncode == 0:
                    logger.info("Successfully activated existing hotspot profile")
                    self.ap_active = True
                    
                    # Only restart NetworkManager if AP activation was successful
                    if self.ap_active:
                        logger.info("AP mode activated, restarting NetworkManager to ensure proper configuration")
                        try:
                            subprocess.run(
                                ["sudo", "systemctl", "restart", "NetworkManager"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=False,
                                timeout=AP_COMMAND_TIMEOUT
                            )
                            time.sleep(WIFI_ON_WAIT)  # Wait for NetworkManager to be ready
                            logger.info("Successfully restarted NetworkManager")
                        except Exception as e:
                            logger.error(f"Failed to restart NetworkManager: {e}")
                    
                    return True
                else:
                    logger.warning(f"Failed to activate existing hotspot: {activate_result.stderr}")
                    logger.info("Will try creating a new hotspot profile")
                    # Don't return here, fall through to create a new profile
            
            # Create a new connection profile for the hotspot with our desired IP
            logger.info("Creating new hotspot profile")
            
            # Try two methods to create the AP - first with custom IP, then fallback to simple method
            methods_to_try = [
                {
                    "name": "Custom IP method",
                    "cmd": [
                        "nmcli", "connection", "add",
                        "type", "wifi",
                        "ifname", "wlan0",
                        "con-name", conn_name,
                        "autoconnect", "no",
                        "ssid", AP_SSID,
                        "mode", "ap",
                        "ipv4.method", "shared",
                        "ipv4.addresses", f"{AP_IP_ADDRESS}/24"
                    ] + ([] if OPEN_AP else ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", AP_PASSWORD]),
                    "activate_cmd": ["nmcli", "connection", "up", conn_name]
                },
                {
                    "name": "Simple hotspot method",
                    "cmd": [
                        "nmcli", "device", "wifi", "hotspot", 
                        "ifname", "wlan0", 
                        "ssid", AP_SSID
                    ] + ([] if OPEN_AP else ["password", AP_PASSWORD]),
                    "activate_cmd": None  # Simple method activates automatically
                },
                {
                    "name": "Direct hostapd method",
                    "cmd": None,  # This will be a different approach handled separately
                    "activate_cmd": None
                }
            ]
            
            # Try each method until one succeeds
            for method in methods_to_try:
                if method["name"] == "Direct hostapd method":
                    # Skip this method for now
                    continue
                    
                logger.info(f"Trying AP activation with: {method['name']}")
                
                if method["cmd"] is None:
                    continue
                    
                # Execute the command to create/setup the AP
                create_result = subprocess.run(
                    method["cmd"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=AP_COMMAND_TIMEOUT
                )
                
                if create_result.returncode != 0:
                    logger.warning(f"Failed with {method['name']}: {create_result.stderr}")
                    continue
                    
                # If this method requires activation, do it
                if method["activate_cmd"] is not None:
                    activate_result = subprocess.run(
                        method["activate_cmd"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        timeout=AP_COMMAND_TIMEOUT
                    )
                    
                    if activate_result.returncode != 0:
                        logger.warning(f"Failed to activate with {method['name']}: {activate_result.stderr}")
                        continue
                
                # Check if AP is now active
                time.sleep(AP_ACTIVATION_WAIT)  # Give system a moment to complete activation
                if self.is_ap_active():
                    logger.info(f"AP mode activated successfully with {method['name']}")
                    self.ap_active = True
                    
                    # Only restart NetworkManager if AP activation was successful
                    if self.ap_active:
                        logger.info("AP mode activated, restarting NetworkManager to ensure proper configuration")
                        try:
                            subprocess.run(
                                ["sudo", "systemctl", "restart", "NetworkManager"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=False,
                                timeout=AP_COMMAND_TIMEOUT
                            )
                            time.sleep(WIFI_ON_WAIT)  # Wait for NetworkManager to be ready
                            logger.info("Successfully restarted NetworkManager")
                        except Exception as e:
                            logger.error(f"Failed to restart NetworkManager: {e}")
                    
                    return True
                else:
                    logger.warning(f"AP appears to not be active after using {method['name']}")
            
            # If we get here, all methods failed
            logger.error("All AP activation methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error activating AP mode: {e}")
            return False
    
    def deactivate_ap(self) -> bool:
        """Deactivate AP mode without deleting the profile."""
        if not self.ap_active:
            logger.info("AP mode already inactive")
            return True
        
        logger.info("Deactivating AP mode")
        
        try:
            # Find the hotspot connection
            conn_name = f"Hotspot-{AP_SSID}"
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,UUID", "connection", "show"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            hotspot_uuid = None
            for line in result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and (parts[0] == conn_name or parts[0] == f"Hotspot {AP_SSID}"):
                    hotspot_uuid = parts[1]
                    break
            
            if not hotspot_uuid:
                logger.warning("Could not find hotspot connection to deactivate")
                self.ap_active = False
                return True
                
            # Deactivate the hotspot (but don't delete it)
            result = subprocess.run(
                ["nmcli", "connection", "down", hotspot_uuid],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to deactivate AP mode: {result.stderr}")
                return False
            
            logger.info("AP mode deactivated successfully (profile preserved)")
            self.ap_active = False
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating AP mode: {e}")
            return False
    
    def display_status(self):
        """Display current status information."""
        status_lines = [
            f"AP Mode: {'Active' if self.ap_active else 'Inactive'}",
            f"AP SSID: {AP_SSID}",
            f"WiFi Connection: {self.current_wifi if self.current_wifi else 'Not connected'}",
            f"Clients Connected: {'Yes' if self.has_connected_clients() else 'No'}",
            f"Force AP Mode: {'Yes' if FORCE_AP_MODE else 'No'}",
            f"Check Interval: {CHECK_INTERVAL} seconds"
        ]
        
        status = "\n".join(status_lines)
        logger.info(f"Status:\n{status}")
    
    def restart_wifi_interface(self):
        """Forcefully restart the WiFi interface if it seems to be in a bad state."""
        logger.info("Forcefully restarting WiFi interface")
        try:
            # First try using nmcli to restart
            subprocess.run(
                ["nmcli", "radio", "wifi", "off"],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            time.sleep(WIFI_OFF_WAIT)
            subprocess.run(
                ["nmcli", "radio", "wifi", "on"],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            # If that didn't work, try using ip link
            ip_check = subprocess.run(
                ["ip", "link", "show", "wlan0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            
            if "state DOWN" in ip_check.stdout:
                logger.info("Interface is DOWN, bringing it up with ip link")
                subprocess.run(
                    ["ip", "link", "set", "wlan0", "up"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=COMMAND_TIMEOUT
                )
            
            # Wait for interface to stabilize
            time.sleep(WIFI_ON_WAIT)
            
            # Log the current state
            state_check = subprocess.run(
                ["ip", "link", "show", "wlan0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT
            )
            logger.info(f"WiFi interface state after restart: {'UP' if 'state UP' in state_check.stdout else 'DOWN'}")
            
            return "state UP" in state_check.stdout
            
        except Exception as e:
            logger.error(f"Error restarting WiFi interface: {e}")
            return False
    
    def run(self):
        """Main execution loop."""
        logger.info("Starting WiPi service")
        logger.info(f"Using SSID: {AP_SSID}")
        
        # Initial check - if not connected to WiFi, immediately activate AP
        if not self.is_wifi_connected():
            logger.info("Not connected to WiFi on startup, activating AP mode")
            ap_success = self.activate_ap()
            if not ap_success:
                logger.error("Failed to activate AP mode on startup, will retry in main loop")
        
        disconnected_count = 0  # Counter for consecutive disconnected states
        last_connection_check = 0
        consecutive_failures = 0  # Count consecutive failures to detect stuck interface
        last_connected_time = time.time()  # Track when we were last connected
        
        while self.running:
            try:
                # Update current status
                self.update_status()
                
                # Check if we should force AP mode
                if FORCE_AP_MODE:
                    logger.info("Forcing AP mode as configured")
                    if not self.ap_active:
                        self.activate_ap()
                    time.sleep(FORCE_AP_SLEEP_INTERVAL)
                    continue
                
                # Check WiFi connection state - primary check
                is_connected = self.is_wifi_connected()
                current_time = time.time()
                
                if is_connected:
                    # We're connected - reset counters and update timestamp
                    disconnected_count = 0
                    consecutive_failures = 0
                    last_connected_time = current_time
                    
                    # If we're connected to WiFi but AP is active and no clients
                    if self.ap_active and not self.has_connected_clients():
                        logger.info("Connected to WiFi and no clients on AP, deactivating AP")
                        self.deactivate_ap()
                else:
                    # Not connected - increment counters
                    disconnected_count += 1
                    consecutive_failures += 1
                    
                    # Log with different levels based on how long we've been disconnected
                    if disconnected_count == 1:
                        logger.debug("WiFi appears disconnected, will confirm")
                    elif disconnected_count == 2:
                        logger.info("WiFi disconnection confirmed, preparing to activate AP mode")
                    else:
                        logger.debug(f"WiFi still disconnected (count: {disconnected_count})")
                    
                    # Calculate time since last connection
                    time_since_connected = current_time - last_connected_time
                    logger.debug(f"Time since last connected: {time_since_connected:.1f} seconds")
                    
                    # If we've had too many consecutive failures, try restarting the interface
                    if consecutive_failures >= INTERFACE_RESTART_THRESHOLD:
                        logger.warning("Multiple consecutive connection failures, restarting WiFi interface")
                        self.restart_wifi_interface()
                        consecutive_failures = 0  # Reset counter
                    
                    # After 2 consecutive disconnected states or 30 seconds since last connection,
                    # activate AP mode if it's not already active
                    if (disconnected_count >= DISCONNECT_COUNT_THRESHOLD or 
                        time_since_connected > DISCONNECT_TIME_THRESHOLD) and not self.ap_active:
                        logger.info(f"WiFi disconnected for {time_since_connected:.1f} seconds, activating AP mode")
                        ap_success = self.activate_ap()
                        if not ap_success:
                            logger.error("Failed to activate AP mode after disconnection, will retry")
                
                # Deal with clients connected to AP - keep AP active if clients are connected
                if self.ap_active and self.has_connected_clients():
                    logger.info("Clients are connected to the AP, maintaining AP mode")
                    # Skip network scanning to avoid disrupting clients
                    time.sleep(MAIN_LOOP_INTERVAL)
                    continue
                
                # Periodic scanning for known networks
                if not is_connected and (current_time - last_connection_check >= CHECK_INTERVAL):
                    logger.info("Performing scheduled scan for known networks")
                    available_networks = self.scan_for_known_networks()
                    last_connection_check = current_time
                    
                    if available_networks:
                        # Try to connect to the first available known network
                        logger.info(f"Found known network {available_networks[0]}, attempting to connect")
                        if self.connect_to_wifi(available_networks[0]):
                            logger.info("Successfully connected to known network")
                            # Keep AP mode active until we confirm connection is stable
                            disconnected_count = 0  # Reset counter
                        else:
                            logger.info("Failed to connect to known network, maintaining AP mode")
                            # Ensure AP is active
                            if not self.ap_active:
                                self.activate_ap()
                    else:
                        logger.info("No known networks found, maintaining AP mode")
                        # Ensure AP is active
                        if not self.ap_active:
                            self.activate_ap()
                
                # Display current status
                self.display_status()
                
                # Sleep for a short interval to be responsive
                logger.debug(f"Sleeping for {MAIN_LOOP_INTERVAL} seconds before next check")
                for _ in range(MAIN_LOOP_INTERVAL):  # Convert to integer for range
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # If we hit an error, make sure AP is active as a fallback
                if not self.ap_active:
                    logger.info("Error occurred, ensuring AP is active as fallback")
                    self.activate_ap()
                time.sleep(ERROR_SLEEP_INTERVAL)  # Brief sleep before retrying

        logger.info("WiPi service stopped")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="WiPi - Automatic WiFi/AP Mode Switching")
    parser.add_argument("-f", "--force-ap", action="store_true", help="Force AP mode")
    parser.add_argument("-s", "--status", action="store_true", help="Display status and exit")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-o", "--open-ap", action="store_true", help="Create an open (no password) access point")
    parser.add_argument("-p", "--prioritize-clients", action="store_true", 
                        help="Prioritize client connections over WiFi connectivity")
    
    return parser.parse_args()


def main():
    """Main entry point."""
    global FORCE_AP_MODE, OPEN_AP, PRIORITIZE_CLIENTS
    
    # Parse command-line arguments
    args = parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Set global flags
    FORCE_AP_MODE = args.force_ap
    OPEN_AP = args.open_ap
    PRIORITIZE_CLIENTS = args.prioritize_clients
    
    # Create WiPi instance
    wipi = WiPi()
    
    # If status flag is set, just display status and exit
    if args.status:
        wipi.update_status()
        wipi.display_status()
        return
    
    # Run the main loop
    wipi.run()


if __name__ == "__main__":
    main()

