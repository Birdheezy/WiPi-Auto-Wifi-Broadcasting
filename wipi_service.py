#!/usr/bin/env python3
"""
WiPi Service Wrapper
Runs the WiPi auto WiFi broadcasting service as a daemon.
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
from pathlib import Path

# Import the WiPi class from wipi.py
try:
    from wipi import WiPi
except ImportError:
    # If running from a different directory, try to find wipi.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(script_dir)
    from wipi import WiPi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/wipi_service.log', mode='a')
    ]
)
logger = logging.getLogger('wipi_service')

def create_pid_file(pid_file):
    """Create a PID file for the service."""
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.debug(f"Created PID file: {pid_file}")
    except Exception as e:
        logger.error(f"Failed to create PID file: {e}")

def remove_pid_file(pid_file):
    """Remove the PID file when the service stops."""
    try:
        if os.path.exists(pid_file):
            os.remove(pid_file)
            logger.debug(f"Removed PID file: {pid_file}")
    except Exception as e:
        logger.error(f"Failed to remove PID file: {e}")

def is_service_running(pid_file):
    """Check if the service is already running."""
    if not os.path.exists(pid_file):
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process with this PID exists
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, FileNotFoundError):
        # Process not running or PID file is invalid
        return False
    except Exception as e:
        logger.error(f"Error checking if service is running: {e}")
        return False

def install_systemd_service():
    """Install WiPi as a systemd service."""
    try:
        # Get the absolute path to the wipi_service.py script
        script_path = os.path.abspath(__file__)
        
        # Create the service file content
        service_content = f"""[Unit]
Description=WiPi Auto WiFi Broadcasting Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 {script_path} --daemon
Restart=on-failure
User=root
Group=root
Type=simple

[Install]
WantedBy=multi-user.target
"""
        
        # Write the service file
        service_file = "/etc/systemd/system/wipi.service"
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        # Set permissions
        os.chmod(service_file, 0o644)
        
        # Reload systemd, enable and start the service
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", "wipi.service"], check=True)
        subprocess.run(["systemctl", "start", "wipi.service"], check=True)
        
        logger.info("WiPi service installed and started successfully")
        print("WiPi service installed and started successfully")
        print("You can check its status with: systemctl status wipi.service")
        return True
    
    except Exception as e:
        logger.error(f"Failed to install systemd service: {e}")
        print(f"Error: Failed to install systemd service: {e}")
        return False

def uninstall_systemd_service():
    """Uninstall the WiPi systemd service."""
    try:
        # Stop and disable the service
        subprocess.run(["systemctl", "stop", "wipi.service"], check=False)
        subprocess.run(["systemctl", "disable", "wipi.service"], check=False)
        
        # Remove the service file
        service_file = "/etc/systemd/system/wipi.service"
        if os.path.exists(service_file):
            os.remove(service_file)
        
        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=False)
        
        logger.info("WiPi service uninstalled successfully")
        print("WiPi service uninstalled successfully")
        return True
    
    except Exception as e:
        logger.error(f"Failed to uninstall systemd service: {e}")
        print(f"Error: Failed to uninstall systemd service: {e}")
        return False

def run_daemon(config_path):
    """Run WiPi as a daemon process."""
    # PID file path
    pid_dir = "/var/run"
    if not os.path.exists(pid_dir) or not os.access(pid_dir, os.W_OK):
        pid_dir = "/tmp"
    pid_file = os.path.join(pid_dir, "wipi.pid")
    
    # Check if already running
    if is_service_running(pid_file):
        logger.error("WiPi service is already running")
        print("Error: WiPi service is already running")
        return False
    
    # Create PID file
    create_pid_file(pid_file)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        remove_pid_file(pid_file)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize and run WiPi
        wipi = WiPi(config_path=config_path)
        logger.info("Starting WiPi daemon")
        wipi.run()
    except Exception as e:
        logger.error(f"Error in WiPi daemon: {e}")
    finally:
        # Clean up
        remove_pid_file(pid_file)
    
    return True

def main():
    """Main entry point for the service wrapper."""
    parser = argparse.ArgumentParser(description="WiPi Service Wrapper")
    parser.add_argument("-c", "--config", default="/home/pi/wipi/config.json", help="Path to configuration file")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run as a daemon")
    parser.add_argument("--install", action="store_true", help="Install as a systemd service")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the systemd service")
    parser.add_argument("--status", action="store_true", help="Check if the service is running")
    args = parser.parse_args()
    
    # Create config directory if it doesn't exist
    config_dir = os.path.dirname(args.config)
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")
    
    # Handle command line arguments
    if args.install:
        return install_systemd_service()
    elif args.uninstall:
        return uninstall_systemd_service()
    elif args.status:
        pid_file = "/var/run/wipi.pid"
        if not os.path.exists(pid_file):
            pid_file = "/tmp/wipi.pid"
        
        if is_service_running(pid_file):
            print("WiPi service is running")
            return True
        else:
            print("WiPi service is not running")
            return False
    elif args.daemon:
        return run_daemon(args.config)
    else:
        # If no specific action, run WiPi directly (not as a daemon)
        wipi = WiPi(config_path=args.config)
        wipi.run()
        return True

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
