#!/bin/bash
#
# WiPi - Auto WiFi Broadcasting
# Installation Script
#

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Function to print section headers
print_section_header() {
    local title="$1"
    echo ""
    echo -e "${BLUE}${BOLD}=== ${YELLOW}${title} ${BLUE}===${NC}"
    echo ""
}

# Function to print status messages
print_status() {
    echo -e "${CYAN}$1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}! $1${NC}"
}

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root"
        echo -e "Please run with: ${BOLD}sudo bash $0${NC}"
        exit 1
    fi
}

# Function to check if NetworkManager is installed
check_network_manager() {
    if ! command -v nmcli &> /dev/null; then
        print_error "NetworkManager is not installed"
        print_status "WiPi requires NetworkManager to function properly"
        
        read -p "Would you like to install NetworkManager now? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            print_status "Installing NetworkManager..."
            apt-get update
            apt-get install -y network-manager
            
            if [ $? -eq 0 ]; then
                print_success "NetworkManager installed successfully"
            else
                print_error "Failed to install NetworkManager"
                exit 1
            fi
        else
            print_warning "NetworkManager is required for WiPi to function"
            print_warning "Installation aborted"
            exit 1
        fi
    else
        print_success "NetworkManager is installed"
    fi
}

# Function to install required Python packages
install_python_packages() {
    print_status "Installing required Python packages..."
    
    # Check if we're in a virtual environment (either directly or via sudo -E)
    if [ -n "$VIRTUAL_ENV" ]; then
        print_status "Using active virtual environment: $VIRTUAL_ENV"
        
        # Use the virtual environment's pip directly
        VENV_PIP="$VIRTUAL_ENV/bin/pip"
        
        if [ -f "$VENV_PIP" ]; then
            print_status "Using pip from: $VENV_PIP"
            
            # Install required packages in the virtual environment
            "$VENV_PIP" install setuptools wheel
            
            if [ $? -eq 0 ]; then
                print_success "Python packages installed successfully in virtual environment"
            else
                print_error "Failed to install Python packages in virtual environment"
                exit 1
            fi
        else
            print_error "Could not find pip in virtual environment: $VENV_PIP"
            exit 1
        fi
    # Check if we're running with sudo -E and the original user had a virtual environment
    elif [ -n "$SUDO_USER" ]; then
        # Try to detect the user's virtual environment
        USER_VENV=$(sudo -u $SUDO_USER bash -c 'echo $VIRTUAL_ENV')
        
        if [ -n "$USER_VENV" ]; then
            print_status "Detected virtual environment from user session: $USER_VENV"
            
            # Use the virtual environment's pip
            VENV_PIP="$USER_VENV/bin/pip"
            
            if [ -f "$VENV_PIP" ]; then
                print_status "Using pip from: $VENV_PIP"
                
                # Install required packages in the virtual environment
                # Use sudo -H to set HOME environment variable correctly
                sudo -H -u $SUDO_USER "$VENV_PIP" install setuptools wheel
                
                if [ $? -eq 0 ]; then
                    print_success "Python packages installed successfully in virtual environment"
                else
                    print_error "Failed to install Python packages in virtual environment"
                    exit 1
                fi
            else
                print_error "Could not find pip in virtual environment: $VENV_PIP"
                exit 1
            fi
        else
            # No virtual environment detected, use system pip with warning
            print_warning "No active virtual environment detected"
            print_status "Using system pip (not recommended for newer Raspberry Pi OS versions)"
            
            # Check if pip3 is available
            if command -v pip3 &> /dev/null; then
                print_status "Using pip3 to install packages"
                
                # Try to install with --break-system-packages flag if needed
                # Use sudo -H to set HOME environment variable correctly
                if sudo -H pip3 install setuptools wheel 2>/dev/null; then
                    print_success "Python packages installed successfully"
                elif sudo -H pip3 install --break-system-packages setuptools wheel 2>/dev/null; then
                    print_success "Python packages installed successfully (using --break-system-packages)"
                    print_warning "Used --break-system-packages flag, which is not recommended"
                    print_warning "Consider using a virtual environment next time"
                else
                    print_error "Failed to install Python packages"
                    print_warning "If you're on a newer Raspberry Pi OS, you may need to activate a virtual environment first"
                    print_warning "or run with the --break-system-packages flag manually"
                    exit 1
                fi
            else
                print_error "pip3 not found"
                print_status "Installing pip..."
                apt-get update
                apt-get install -y python3-pip
                
                # Try again after installing pip
                # Use sudo -H to set HOME environment variable correctly
                if sudo -H pip3 install setuptools wheel 2>/dev/null || sudo -H pip3 install --break-system-packages setuptools wheel 2>/dev/null; then
                    print_success "Python packages installed successfully"
                else
                    print_error "Failed to install Python packages"
                    exit 1
                fi
            fi
        fi
    else
        # No virtual environment and not running with sudo -E
        print_warning "No active virtual environment detected"
        print_status "Using system pip (not recommended for newer Raspberry Pi OS versions)"
        
        # Check if pip3 is available
        if command -v pip3 &> /dev/null; then
            print_status "Using pip3 to install packages"
            
            # Try to install with --break-system-packages flag if needed
            # Use sudo -H to set HOME environment variable correctly
            if sudo -H pip3 install setuptools wheel 2>/dev/null; then
                print_success "Python packages installed successfully"
            elif sudo -H pip3 install --break-system-packages setuptools wheel 2>/dev/null; then
                print_success "Python packages installed successfully (using --break-system-packages)"
                print_warning "Used --break-system-packages flag, which is not recommended"
                print_warning "Consider using a virtual environment next time"
            else
                print_error "Failed to install Python packages"
                print_warning "If you're on a newer Raspberry Pi OS, you may need to activate a virtual environment first"
                print_warning "or run with the --break-system-packages flag manually"
                exit 1
            fi
        else
            print_error "pip3 not found"
            print_status "Installing pip..."
            apt-get update
            apt-get install -y python3-pip
            
            # Try again after installing pip
            # Use sudo -H to set HOME environment variable correctly
            if sudo -H pip3 install setuptools wheel 2>/dev/null || sudo -H pip3 install --break-system-packages setuptools wheel 2>/dev/null; then
                print_success "Python packages installed successfully"
            else
                print_error "Failed to install Python packages"
                exit 1
            fi
        fi
    fi
}

# Function to install WiPi files
install_wipi_files() {
    print_status "Installing WiPi files..."
    
    # Get the directory of the install script
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    
    # Copy files
    cp "$SCRIPT_DIR/wipi.py" /usr/local/bin/wipi.py
    cp "$SCRIPT_DIR/wipi_service.py" /usr/local/bin/wipi_service.py
    
    # Make executable
    chmod +x /usr/local/bin/wipi.py
    chmod +x /usr/local/bin/wipi_service.py
    
    # Create symlinks
    ln -sf /usr/local/bin/wipi.py /usr/local/bin/wipi
    ln -sf /usr/local/bin/wipi_service.py /usr/local/bin/wipi-service
    
    print_success "WiPi files installed successfully"
}

# Function to configure WiPi
configure_wipi() {
    print_section_header "WiPi Configuration"
    
    # Ask for AP SSID
    read -p "$(echo -e "${CYAN}Enter the Access Point SSID [METAR-Pi]: ${NC}")" ap_ssid
    ap_ssid=${ap_ssid:-METAR-Pi}
    
    # Ask for AP password
    read -p "$(echo -e "${CYAN}Enter the Access Point password [METAR-Pi]: ${NC}")" ap_password
    ap_password=${ap_password:-METAR-Pi}
    
    # Ask for AP IP address
    read -p "$(echo -e "${CYAN}Enter the Access Point IP address [192.168.8.1]: ${NC}")" ap_ip
    ap_ip=${ap_ip:-192.168.8.1}
    
    # Update config file
    cat > /home/pi/wipi/config.json << EOF
{
    "ap_ssid": "$ap_ssid",
    "ap_password": "$ap_password",
    "ap_ip_address": "$ap_ip",
    "check_interval": 120,
    "force_ap_mode": false,
    "debug_mode": false,
    "ap_channel": 6,
    "ap_band": "bg",
    "ap_hidden": false,
    "reconnect_attempts": 3,
    "reconnect_delay": 5,
    "preferred_networks": [],
    "prioritize_clients": true,
    "ap_open": false
}
EOF
    
    print_success "WiPi configured successfully"
}

# Function to install systemd service
install_service() {
    print_status "Installing WiPi service..."
    
    # Check if we're in a virtual environment or if one was detected from the user
    VENV_PATH=""
    if [ -n "$VIRTUAL_ENV" ]; then
        VENV_PATH="$VIRTUAL_ENV"
    elif [ -n "$SUDO_USER" ]; then
        USER_VENV=$(sudo -u $SUDO_USER bash -c 'echo $VIRTUAL_ENV')
        if [ -n "$USER_VENV" ]; then
            VENV_PATH="$USER_VENV"
        fi
    fi
    
    # Create a systemd service file
    if [ -n "$VENV_PATH" ]; then
        print_status "Configuring service to use virtual environment: $VENV_PATH"
        cat > /etc/systemd/system/wipi.service << EOF
[Unit]
Description=WiPi Auto WiFi Broadcasting
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=$VENV_PATH/bin/python3 /home/pi/wipi/wipi_service.py --daemon --config /home/pi/wipi/config.json
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    else
        cat > /etc/systemd/system/wipi.service << EOF
[Unit]
Description=WiPi Auto WiFi Broadcasting
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/pi/wipi/wipi_service.py --daemon --config /home/pi/wipi/config.json
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    # Reload systemd, enable and start the service
    systemctl daemon-reload
    systemctl enable wipi.service
    systemctl start wipi.service
    
    if [ $? -eq 0 ]; then
        print_success "WiPi service installed successfully"
    else
        print_error "Failed to install WiPi service"
        exit 1
    fi
}

# Function to create aliases
create_aliases() {
    print_status "Creating command aliases..."
    
    # Check if we're in a virtual environment or if one was detected from the user
    VENV_PATH=""
    if [ -n "$VIRTUAL_ENV" ]; then
        VENV_PATH="$VIRTUAL_ENV"
    elif [ -n "$SUDO_USER" ]; then
        USER_VENV=$(sudo -u $SUDO_USER bash -c 'echo $VIRTUAL_ENV')
        if [ -n "$USER_VENV" ]; then
            VENV_PATH="$USER_VENV"
        fi
    fi
    
    # Create aliases file with or without virtual environment
    if [ -n "$VENV_PATH" ]; then
        print_status "Configuring aliases to use virtual environment: $VENV_PATH"
        cat > /etc/profile.d/wipi-aliases.sh << EOF
# WiPi command aliases
alias wipi-status='systemctl status wipi.service'
alias wipi-start='sudo systemctl start wipi.service'
alias wipi-stop='sudo systemctl stop wipi.service'
alias wipi-restart='sudo systemctl restart wipi.service'
alias wipi-enable='sudo systemctl enable wipi.service'
alias wipi-disable='sudo systemctl disable wipi.service'
alias wipi-log='sudo journalctl -u wipi.service'
alias wipi-config='sudo nano /home/pi/wipi/config.json'
alias wipi='sudo $VENV_PATH/bin/python3 /home/pi/wipi/wipi.py --config /home/pi/wipi/config.json'
alias wipi-uninstall='sudo systemctl stop wipi.service && sudo systemctl disable wipi.service && sudo rm -rf /home/pi/wipi /etc/systemd/system/wipi.service /etc/profile.d/wipi-aliases.sh && echo -e "\033[0;32m✓ WiPi has been uninstalled\033[0m"'
EOF
    else
        cat > /etc/profile.d/wipi-aliases.sh << EOF
# WiPi command aliases
alias wipi-status='systemctl status wipi.service'
alias wipi-start='sudo systemctl start wipi.service'
alias wipi-stop='sudo systemctl stop wipi.service'
alias wipi-restart='sudo systemctl restart wipi.service'
alias wipi-enable='sudo systemctl enable wipi.service'
alias wipi-disable='sudo systemctl disable wipi.service'
alias wipi-log='sudo journalctl -u wipi.service'
alias wipi-config='sudo nano /home/pi/wipi/config.json'
alias wipi='sudo /usr/bin/python3 /home/pi/wipi/wipi.py --config /home/pi/wipi/config.json'
alias wipi-uninstall='sudo systemctl stop wipi.service && sudo systemctl disable wipi.service && sudo rm -rf /home/pi/wipi /etc/systemd/system/wipi.service /etc/profile.d/wipi-aliases.sh && echo -e "\033[0;32m✓ WiPi has been uninstalled\033[0m"'
EOF
    fi
    
    # Make executable
    chmod +x /etc/profile.d/wipi-aliases.sh
    
    print_success "Command aliases created"
    print_status "Aliases will be available after next login or after running:"
    print_status "source /etc/profile.d/wipi-aliases.sh"
}

# Function to display completion message
display_completion() {
    print_section_header "Installation Complete"
    
    echo -e "${GREEN}WiPi has been successfully installed!${NC}"
    echo ""
    echo -e "Access Point SSID: ${BOLD}${YELLOW}$ap_ssid${NC}"
    echo -e "Access Point Password: ${BOLD}${YELLOW}$ap_password${NC}"
    echo -e "Access Point IP: ${BOLD}${YELLOW}$ap_ip${NC}"
    echo ""
    echo -e "${CYAN}Available commands:${NC}"
    echo -e "  ${BOLD}wipi-status${NC} - Check service status"
    echo -e "  ${BOLD}wipi-start${NC} - Start the service"
    echo -e "  ${BOLD}wipi-stop${NC} - Stop the service"
    echo -e "  ${BOLD}wipi-restart${NC} - Restart the service"
    echo -e "  ${BOLD}wipi-log${NC} - View service logs"
    echo -e "  ${BOLD}wipi-config${NC} - Edit configuration"
    echo -e "  ${BOLD}wipi-uninstall${NC} - Completely remove WiPi"
    echo ""
    echo -e "${YELLOW}Note:${NC} When the Raspberry Pi cannot connect to a known WiFi network,"
    echo -e "it will automatically create an access point with the configured settings."
    echo -e "You can then connect to this access point to access your Pi."
    echo ""
    echo -e "To manually force AP mode: ${BOLD}sudo wipi --force-ap${NC}"
    echo -e "To check current status: ${BOLD}sudo wipi --status${NC}"
    echo ""
    echo -e "To uninstall WiPi: ${BOLD}sudo bash $0 --uninstall${NC}"
    echo ""
}

# Function to uninstall WiPi
uninstall_wipi() {
    print_section_header "WiPi Uninstallation"
    
    # Confirm uninstallation
    read -p "Are you sure you want to uninstall WiPi? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Uninstallation cancelled"
        exit 0
    fi
    
    print_status "Stopping and removing WiPi service..."
    
    # Stop and disable the service
    systemctl stop wipi.service 2>/dev/null
    systemctl disable wipi.service 2>/dev/null
    
    # Remove the service file
    if [ -f /etc/systemd/system/wipi.service ]; then
        rm /etc/systemd/system/wipi.service
        systemctl daemon-reload
        print_success "WiPi service removed"
    fi
    
    # Remove WiPi files
    print_status "Removing WiPi files..."
    
    # Remove binaries and symlinks
    rm -f /usr/local/bin/wipi.py
    rm -f /usr/local/bin/wipi_service.py
    rm -f /usr/local/bin/wipi
    rm -f /usr/local/bin/wipi-service
    
    # Ask about configuration
    read -p "Do you want to remove WiPi configuration files? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf /etc/wipi
        print_success "Configuration files removed"
    else
        print_warning "Configuration files preserved at /etc/wipi"
    fi
    
    # Remove aliases
    if [ -f /etc/profile.d/wipi-aliases.sh ]; then
        rm -f /etc/profile.d/wipi-aliases.sh
        print_success "Command aliases removed"
    fi
    
    print_section_header "Uninstallation Complete"
    echo -e "${GREEN}WiPi has been successfully uninstalled.${NC}"
    echo ""
    echo -e "${YELLOW}Note:${NC} NetworkManager remains installed as it may be used by other applications."
    echo -e "If you want to remove it, you can run: ${BOLD}sudo apt remove network-manager${NC}"
    echo ""
}

# Main installation function
main() {
    # Fix line endings if needed
    if grep -q $'\r' "$0"; then
        echo "Fixing line endings..."
        sed -i 's/\r$//' "$0"
        exec "$0" "$@"
    fi
    
    # Check for uninstall flag
    if [ "$1" == "--uninstall" ]; then
        check_root
        uninstall_wipi
        exit 0
    fi
    
    print_section_header "WiPi - Auto WiFi Broadcasting Installation"
    
    # Check if running as root
    check_root
    
    # Check for NetworkManager
    check_network_manager
    
    # Check if a virtual environment is active
    if [ -z "$VIRTUAL_ENV" ]; then
        # Try to detect virtual environment from user session if running with sudo
        USER_VENV=""
        if [ -n "$SUDO_USER" ]; then
            USER_VENV=$(sudo -u $SUDO_USER bash -c 'echo $VIRTUAL_ENV')
        fi
        
        if [ -z "$USER_VENV" ]; then
            print_warning "No active virtual environment detected"
            echo ""
            echo -e "${YELLOW}Using a virtual environment is strongly recommended for this installation.${NC}"
            echo -e "${YELLOW}This prevents conflicts with system Python packages and avoids the need${NC}"
            echo -e "${YELLOW}for the --break-system-packages flag on newer Raspberry Pi OS versions.${NC}"
            echo ""
            
            read -p "$(echo -e "${CYAN}Do you have a virtual environment activated? [y/N]: ${NC}")" VENV_ACTIVE
            if [[ ! $VENV_ACTIVE =~ ^[Yy]$ ]]; then
                echo ""
                echo -e "${YELLOW}Please follow these steps to create and activate a virtual environment:${NC}"
                echo ""
                echo -e "${CYAN}1. Exit this installer:${NC}"
                echo -e "   Press Ctrl+C"
                echo ""
                echo -e "${CYAN}2. Create a virtual environment (if you don't already have one):${NC}"
                echo -e "   ${GREEN}python3 -m venv ~/metar${NC}"
                echo ""
                echo -e "${CYAN}3. Activate the virtual environment:${NC}"
                echo -e "   ${GREEN}source ~/metar/bin/activate${NC}"
                echo ""
                echo -e "${CYAN}4. Run this installer again with sudo -E:${NC}"
                echo -e "   ${GREEN}sudo -E bash install.sh${NC}"
                echo ""
                echo -e "${YELLOW}The -E flag preserves your environment variables, including the virtual environment.${NC}"
                echo ""
                
                # Ask if they want to continue anyway
                read -p "$(echo -e "${CYAN}Do you want to continue anyway (not recommended)? [y/N]: ${NC}")" CONTINUE_ANYWAY
                if [[ ! $CONTINUE_ANYWAY =~ ^[Yy]$ ]]; then
                    print_warning "Installation aborted"
                    exit 0
                fi
                
                print_warning "Continuing without a virtual environment (not recommended)"
            else
                print_warning "You indicated a virtual environment is active, but it was not detected"
                print_warning "This may be due to running with sudo without the -E flag"
                echo ""
                echo -e "${YELLOW}Please run the installer with:${NC}"
                echo -e "${GREEN}sudo -E bash install.sh${NC}"
                echo ""
                
                # Ask if they want to continue anyway
                read -p "$(echo -e "${CYAN}Do you want to continue anyway (not recommended)? [y/N]: ${NC}")" CONTINUE_ANYWAY
                if [[ ! $CONTINUE_ANYWAY =~ ^[Yy]$ ]]; then
                    print_warning "Installation aborted"
                    exit 0
                fi
                
                print_warning "Continuing without a detected virtual environment (not recommended)"
            fi
        else
            print_success "Detected virtual environment from user session: $USER_VENV"
        fi
    else
        print_success "Using active virtual environment: $VIRTUAL_ENV"
    fi
    
    # Install required Python packages
    install_python_packages
    
    # Create temporary directory and download WiPi files
    print_status "Downloading WiPi files from repository..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # Clone the repository
    if git clone https://github.com/Birdheezy/WiPi-Auto-Wifi-Broadcasting.git > /dev/null 2>&1; then
        print_success "Repository cloned successfully"
        
        # Create wipi directory
        mkdir -p /home/pi/wipi
        
        # Copy files from the cloned repository
        cp "$TEMP_DIR/WiPi-Auto-Wifi-Broadcasting/wipi.py" /home/pi/wipi/wipi.py
        cp "$TEMP_DIR/WiPi-Auto-Wifi-Broadcasting/wipi_service.py" /home/pi/wipi/wipi_service.py
        cp "$TEMP_DIR/WiPi-Auto-Wifi-Broadcasting/config.json" /home/pi/wipi/config.json
        
        # Make executable
        chmod +x /home/pi/wipi/wipi.py
        chmod +x /home/pi/wipi/wipi_service.py
        
        # Set ownership
        chown -R pi:pi /home/pi/wipi
        
        # Clean up
        cd /
        rm -rf "$TEMP_DIR"
        
        print_success "WiPi files installed successfully"
    else
        print_error "Failed to download WiPi files"
        cd /
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    
    # Always run the configuration step
    configure_wipi
    
    # Remove the old config file to avoid dual SSIDs
    if [ -f /etc/wipi/config.json ]; then
        print_status "Removing old configuration file at /etc/wipi/config.json"
        rm -f /etc/wipi/config.json
        print_success "Old configuration file removed"
    fi
    
    # Clean up any existing NetworkManager connections related to WiPi
    print_status "Cleaning up existing NetworkManager connections..."
    
    # Look for connections that might be related to WiPi
    CONNECTIONS=$(nmcli -t -f NAME connection show)
    
    # Delete connections that match the pattern
    for conn in $CONNECTIONS; do
        if [[ "$conn" == "METAR-Pi"* || "$conn" == "Hotspot"* || "$conn" == "AccessPopup"* ]]; then
            print_status "Removing NetworkManager connection: $conn"
            nmcli connection delete "$conn" 2>/dev/null
        fi
    done
    
    print_success "NetworkManager connections cleaned up"
    
    # Install systemd service
    install_service
    
    # Create command aliases
    create_aliases
    
    # Display completion message
    display_completion
}

# Run the main installation function with all arguments
main "$@"
