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
    
    # Check if pip is installed
    if ! command -v pip3 &> /dev/null; then
        print_status "Installing pip..."
        apt-get update
        apt-get install -y python3-pip
    fi
    
    # Install required packages
    pip3 install -q setuptools wheel
    
    if [ $? -eq 0 ]; then
        print_success "Python packages installed successfully"
    else
        print_error "Failed to install Python packages"
        exit 1
    fi
}

# Function to install WiPi files
install_wipi_files() {
    print_status "Installing WiPi files..."
    
    # Create directory structure
    mkdir -p /etc/wipi
    
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
    
    # Copy config file if it doesn't exist
    if [ ! -f /etc/wipi/config.json ]; then
        cp "$SCRIPT_DIR/config.json" /etc/wipi/config.json
    else
        print_warning "Config file already exists at /etc/wipi/config.json"
        print_warning "Your existing configuration will not be modified"
    fi
    
    print_success "WiPi files installed successfully"
}

# Function to configure WiPi
configure_wipi() {
    print_section_header "WiPi Configuration"
    
    # Ask for AP SSID
    read -p "Enter the Access Point SSID [METAR-Pi]: " ap_ssid
    ap_ssid=${ap_ssid:-METAR-Pi}
    
    # Ask for AP password
    read -p "Enter the Access Point password [METAR-Pi]: " ap_password
    ap_password=${ap_password:-METAR-Pi}
    
    # Ask for AP IP address
    read -p "Enter the Access Point IP address [192.168.8.1]: " ap_ip
    ap_ip=${ap_ip:-192.168.8.1}
    
    # Update config file
    cat > /etc/wipi/config.json << EOF
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
    "preferred_networks": []
}
EOF
    
    print_success "WiPi configured successfully"
}

# Function to install systemd service
install_service() {
    print_status "Installing WiPi service..."
    
    # Use the service installation function in wipi_service.py
    python3 /usr/local/bin/wipi_service.py --install
    
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
    
    # Create aliases file
    cat > /etc/profile.d/wipi-aliases.sh << EOF
# WiPi command aliases
alias wipi-status='systemctl status wipi.service'
alias wipi-start='sudo systemctl start wipi.service'
alias wipi-stop='sudo systemctl stop wipi.service'
alias wipi-restart='sudo systemctl restart wipi.service'
alias wipi-enable='sudo systemctl enable wipi.service'
alias wipi-disable='sudo systemctl disable wipi.service'
alias wipi-log='sudo journalctl -u wipi.service'
alias wipi-config='sudo nano /etc/wipi/config.json'
EOF
    
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
    
    # Install required Python packages
    install_python_packages
    
    # Install WiPi files
    install_wipi_files
    
    # Configure WiPi
    configure_wipi
    
    # Install systemd service
    install_service
    
    # Create command aliases
    create_aliases
    
    # Display completion message
    display_completion
}

# Run the main installation function with all arguments
main "$@"
