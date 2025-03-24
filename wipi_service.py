#!/usr/bin/env python3
"""
WiPi Service Wrapper

This script provides a service wrapper for the WiPi application.
It handles daemonization, PID file management, and systemd integration.
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
import atexit
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
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('wipi-service')

# Update the paths to be relative to the installation directory
INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.dirname(INSTALL_DIR)  # This will be set by the installer
PID_FILE = '/var/run/wipi.pid'
LOG_FILE = '/var/log/wipi.log'

# Add a function to activate the venv
def activate_venv():
    """Activate the virtual environment if not already activated."""
    if not hasattr(sys, 'real_prefix') and not hasattr(sys, 'base_prefix'):
        venv_activate = os.path.join(VENV_DIR, 'bin', 'activate_this.py')
        if os.path.exists(venv_activate):
            with open(venv_activate) as f:
                exec(f.read(), {'__file__': venv_activate})


def daemonize():
    """
    Daemonize the process by forking twice and detaching from the terminal.
    """
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit first parent
            sys.exit(0)
    except OSError as e:
        logger.error(f"Fork #1 failed: {e}")
        sys.exit(1)
    
    # Decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)
    
    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit second parent
            sys.exit(0)
    except OSError as e:
        logger.error(f"Fork #2 failed: {e}")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    with open('/dev/null', 'r') as stdin_file:
        os.dup2(stdin_file.fileno(), sys.stdin.fileno())
    
    with open(LOG_FILE, 'a+') as stdout_file:
        os.dup2(stdout_file.fileno(), sys.stdout.fileno())
        os.dup2(stdout_file.fileno(), sys.stderr.fileno())
    
    # Write PID file
    with open(PID_FILE, 'w') as pid_file:
        pid_file.write(str(os.getpid()))
    
    # Register function to remove PID file on exit
    atexit.register(lambda: os.remove(PID_FILE) if os.path.exists(PID_FILE) else None)


def run_daemon():
    """
    Run the WiPi service as a daemon.
    """
    # Check if already running
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as pid_file:
            pid = pid_file.read().strip()
        
        try:
            # Check if process is still running
            os.kill(int(pid), 0)
            logger.error(f"WiPi service is already running with PID {pid}")
            sys.exit(1)
        except (OSError, ValueError):
            # Process not running, remove stale PID file
            logger.warning(f"Removing stale PID file for PID {pid}")
            os.remove(PID_FILE)
    
    # Daemonize the process
    daemonize()
    
    # Run the WiPi service
    wipi = WiPi()
    wipi.run()


def install_systemd_service():
    """
    Install the WiPi service as a systemd service.
    """
    if os.geteuid() != 0:
        logger.error("This command must be run as root")
        sys.exit(1)
    
    # Ensure the installation directory exists
    os.makedirs(INSTALL_DIR, exist_ok=True)
    
    # Get the paths to the scripts
    current_dir = os.path.dirname(os.path.abspath(__file__))
    service_script = os.path.join(INSTALL_DIR, 'wipi_service.py')
    wipi_script = os.path.join(INSTALL_DIR, 'wipi.py')
    
    # Copy the scripts to the installation directory if not already there
    if os.path.abspath(__file__) != service_script:
        logger.info(f"Copying scripts to {INSTALL_DIR}")
        import shutil
        try:
            shutil.copy2(os.path.join(current_dir, 'wipi_service.py'), service_script)
            shutil.copy2(os.path.join(current_dir, 'wipi.py'), wipi_script)
            # Make the scripts executable
            os.chmod(service_script, 0o755)
            os.chmod(wipi_script, 0o755)
            # Set ownership to pi user if running as root
            if os.geteuid() == 0:
                import pwd
                try:
                    pi_uid = pwd.getpwnam('pi').pw_uid
                    pi_gid = pwd.getpwnam('pi').pw_gid
                    os.chown(service_script, pi_uid, pi_gid)
                    os.chown(wipi_script, pi_uid, pi_gid)
                    os.chown(INSTALL_DIR, pi_uid, pi_gid)
                except KeyError:
                    logger.warning("Could not find pi user, not changing ownership")
        except Exception as e:
            logger.error(f"Failed to copy scripts: {e}")
            sys.exit(1)
    
    # Create the service file
    service_content = f"""[Unit]
Description=WiPi Auto WiFi Broadcasting
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 {service_script} --daemon
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    # Write the service file
    service_path = '/etc/systemd/system/wipi.service'
    try:
        with open(service_path, 'w') as service_file:
            service_file.write(service_content)
        
        # Reload systemd and enable the service
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', 'wipi.service'], check=True)
        
        logger.info(f"WiPi service installed at {service_path}")
        logger.info("To start the service, run: sudo systemctl start wipi.service")
    except Exception as e:
        logger.error(f"Failed to install service: {e}")
        sys.exit(1)


def uninstall_systemd_service():
    """
    Uninstall the WiPi systemd service.
    """
    if os.geteuid() != 0:
        logger.error("This command must be run as root")
        sys.exit(1)
    
    service_path = '/etc/systemd/system/wipi.service'
    
    try:
        # Stop and disable the service
        subprocess.run(['systemctl', 'stop', 'wipi.service'], check=False)
        subprocess.run(['systemctl', 'disable', 'wipi.service'], check=False)
        
        # Remove the service file
        if os.path.exists(service_path):
            os.remove(service_path)
            subprocess.run(['systemctl', 'daemon-reload'], check=False)
            logger.info("WiPi service uninstalled successfully")
        else:
            logger.warning(f"Service file {service_path} not found")
    except Exception as e:
        logger.error(f"Failed to uninstall service: {e}")
        sys.exit(1)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="WiPi Service Wrapper")
    
    # Service management options
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--daemon", action="store_true", help="Run as a daemon")
    group.add_argument("--install-service", action="store_true", help="Install systemd service")
    group.add_argument("--uninstall-service", action="store_true", help="Uninstall systemd service")
    group.add_argument("--run", action="store_true", help="Run in foreground (for testing)")
    
    # Logging options
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    return parser.parse_args()


def main():
    """Main entry point."""
    # Activate venv if needed
    activate_venv()
    
    # Parse command-line arguments
    args = parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Process commands
    if args.daemon:
        run_daemon()
    elif args.install_service:
        install_systemd_service()
    elif args.uninstall_service:
        uninstall_systemd_service()
    elif args.run:
        # Run in foreground (for testing)
        wipi = WiPi()
        wipi.run()


if __name__ == "__main__":
    main()
