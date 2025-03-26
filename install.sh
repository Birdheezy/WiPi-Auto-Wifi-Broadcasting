#!/bin/bash

# WiPi Installation Script
# This script installs and configures the WiPi Auto WiFi Broadcasting system

# Default settings
INSTALL_DIR="/home/pi/wipi"
DEFAULT_VENV_NAME="wipi"
DEFAULT_SSID="WiPi"
DEFAULT_PASSWORD="raspberry"
DEFAULT_IP="192.168.8.1"
DEFAULT_CHECK_INTERVAL=30
DEFAULT_LOOP_INTERVAL=15

# Add these as new settings at the top with other defaults
VENV_DIR="${INSTALL_DIR}/venv"
PYTHON_BIN="/usr/bin/python3"

# Add these variables at the top with other settings
GITHUB_RAW_URL="https://raw.githubusercontent.com/yourusername/WiPi-Auto-Wifi-Broadcasting/main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (use sudo)"
    exit 1
fi

# Add a function to handle venv setup
setup_venv() {
    log_info "Virtual Environment Setup"
    echo "------------------------"
    read -p "Do you have an existing virtual environment you'd like to use? (y/N): " use_existing_venv
    use_existing_venv=${use_existing_venv:-n}

    if [[ $use_existing_venv =~ ^[Yy]$ ]]; then
        # Use existing venv
        while true; do
            read -p "Enter the full path to your virtual environment: " VENV_DIR
            if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ]; then
                log_info "Using existing virtual environment at $VENV_DIR"
                break
            else
                log_error "Invalid virtual environment path. Please enter a valid path."
            fi
        done
    else
        # Create new venv in INSTALL_DIR with user-specified name
        read -p "Enter name for new virtual environment [$DEFAULT_VENV_NAME]: " venv_name
        venv_name=${venv_name:-$DEFAULT_VENV_NAME}
        VENV_DIR="${INSTALL_DIR}/${venv_name}"
        
        if [ -d "$VENV_DIR" ]; then
            log_warn "Virtual environment already exists at $VENV_DIR"
            read -p "Would you like to recreate it? (y/N): " recreate_venv
            recreate_venv=${recreate_venv:-n}
            if [[ $recreate_venv =~ ^[Yy]$ ]]; then
                log_info "Removing existing virtual environment..."
                rm -rf "$VENV_DIR"
            else
                log_info "Using existing virtual environment"
                return
            fi
        fi
        
        log_info "Creating new virtual environment at $VENV_DIR..."
        $PYTHON_BIN -m venv "$VENV_DIR"
    fi

    # Just upgrade pip
    log_info "Upgrading pip..."
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip
    deactivate
}

# Function to install dependencies
install_dependencies() {
    log_info "Checking dependencies..."
    
    # Check for NetworkManager
    if ! dpkg -l | grep -q "^ii.*network-manager"; then
        log_info "Installing NetworkManager..."
        apt-get update
        apt-get install -y network-manager
    else
        log_info "NetworkManager is already installed"
    fi
    
    # Check for python3-venv
    if ! dpkg -l | grep -q "^ii.*python3-venv"; then
        log_info "Installing python3-venv..."
        apt-get install -y python3-venv
    else
        log_info "python3-venv is already installed"
    fi
    
    # Set up virtual environment
    setup_venv

    # Add to install_dependencies function
    verify_networkmanager
}

# Function to create and configure WiPi service
create_wipi_service() {
    log_info "Creating WiPi service..."
    cat > /etc/systemd/system/wipi.service << EOF
[Unit]
Description=WiPi Auto WiFi Broadcasting
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/home/pi/wipi/wipi/bin/python /home/pi/wipi/wipi_service.py --daemon
Environment=PYTHONPATH=/home/pi/wipi
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Set correct permissions
    chmod 644 /etc/systemd/system/wipi.service
}

# Function to modify WiPi configuration
configure_wipi() {
    local ssid=$1
    local password=$2
    local ip=$3
    local check_interval=$4
    local loop_interval=$5
    local debug=$6
    local open_ap=$7

    # Create a backup of the original file
    cp "${INSTALL_DIR}/wipi.py" "${INSTALL_DIR}/wipi.py.bak"

    # Update configuration values
    sed -i "s/AP_SSID = \"WiPi\"/AP_SSID = \"${ssid}\"/" "${INSTALL_DIR}/wipi.py"
    sed -i "s/AP_PASSWORD = \"raspberry\"/AP_PASSWORD = \"${password}\"/" "${INSTALL_DIR}/wipi.py"
    sed -i "s/AP_IP_ADDRESS = \"192.168.8.1\"/AP_IP_ADDRESS = \"${ip}\"/" "${INSTALL_DIR}/wipi.py"
    sed -i "s/CHECK_INTERVAL = 30/CHECK_INTERVAL = ${check_interval}/" "${INSTALL_DIR}/wipi.py"
    sed -i "s/MAIN_LOOP_INTERVAL = 15/MAIN_LOOP_INTERVAL = ${loop_interval}/" "${INSTALL_DIR}/wipi.py"

    if [ "$debug" = "y" ]; then
        sed -i "s/level=logging.INFO/level=logging.DEBUG/" "${INSTALL_DIR}/wipi.py"
    fi

    if [ "$open_ap" = "y" ]; then
        sed -i "s/OPEN_AP = False/OPEN_AP = True/" "${INSTALL_DIR}/wipi.py"
    fi
}

# Add this function
update_python_files() {
    local venv_path=$1
    
    # Update wipi_service.py with the correct venv path
    sed -i "s|VENV_DIR = os.path.dirname(INSTALL_DIR)|VENV_DIR = \"${venv_path}\"|" "${INSTALL_DIR}/wipi_service.py"
}

# Function to perform basic installation
basic_install() {
    log_info "Performing basic installation with default settings..."
    
    # Create service
    create_wipi_service
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable and start service
    systemctl enable wipi.service
    systemctl start wipi.service
    
    log_info "Basic installation completed successfully!"
}

# Function to perform advanced installation
advanced_install() {
    log_info "Starting advanced installation..."
    
    # Prompt for configuration
    read -p "Enter AP SSID [$DEFAULT_SSID]: " ssid
    ssid=${ssid:-$DEFAULT_SSID}
    
    read -p "Enter AP Password [$DEFAULT_PASSWORD]: " password
    password=${password:-$DEFAULT_PASSWORD}
    
    read -p "Enter AP IP Address [$DEFAULT_IP]: " ip
    ip=${ip:-$DEFAULT_IP}
    
    read -p "Enter network check interval in seconds [$DEFAULT_CHECK_INTERVAL]: " check_interval
    check_interval=${check_interval:-$DEFAULT_CHECK_INTERVAL}
    
    read -p "Enter main loop interval in seconds [$DEFAULT_LOOP_INTERVAL]: " loop_interval
    loop_interval=${loop_interval:-$DEFAULT_LOOP_INTERVAL}
    
    read -p "Enable debug logging? (y/N): " debug
    debug=${debug:-n}
    
    read -p "Create open AP (no password)? (y/N): " open_ap
    open_ap=${open_ap:-n}
    
    # Configure WiPi
    configure_wipi "$ssid" "$password" "$ip" "$check_interval" "$loop_interval" "$debug" "$open_ap"
    
    # Create service
    create_wipi_service
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable and start service
    systemctl enable wipi.service
    systemctl start wipi.service
    
    log_info "Advanced installation completed successfully!"
}

# Add this function to download files
download_files() {
    log_info "Downloading WiPi files..."
    
    # Create backup first
    backup_config
    
    # Create temporary directory with error handling
    local temp_dir
    temp_dir=$(mktemp -d) || {
        log_error "Failed to create temporary directory"
        exit 1
    }
    
    # Download with better error handling
    local files=("wipi.py" "wipi_service.py")
    for file in "${files[@]}"; do
        if ! curl -s -S -f -o "${temp_dir}/${file}" "${GITHUB_RAW_URL}/${file}"; then
            log_error "Failed to download ${file}"
            rm -rf "${temp_dir}"
            exit 1
        fi
    done
    
    # Verify files before copying
    for file in "${files[@]}"; do
        if [ ! -s "${temp_dir}/${file}" ]; then
            log_error "Downloaded file ${file} is empty"
            rm -rf "${temp_dir}"
            exit 1
        fi
    done
    
    # Create installation directory with error handling
    mkdir -p "$INSTALL_DIR" || {
        log_error "Failed to create installation directory"
        rm -rf "${temp_dir}"
        exit 1
    }
    
    # Copy files with error handling
    cp "${temp_dir}"/* "$INSTALL_DIR/" || {
        log_error "Failed to copy files to installation directory"
        rm -rf "${temp_dir}"
        exit 1
    }
    
    # Cleanup
    rm -rf "${temp_dir}"
    
    # Set permissions with error handling
    chmod 755 "$INSTALL_DIR"/*.py || log_error "Failed to set file permissions"
    chown -R pi:pi "$INSTALL_DIR" || log_error "Failed to set file ownership"
    
    log_info "Files downloaded and installed successfully"
}

# Move this function up with other functions, before the main installation process
setup_aliases() {
    log_info "Setting up WiPi command aliases..."
    
    # Define the aliases we want to add
    local aliases=(
        "# WiPi aliases"
        "alias wipi-status='sudo systemctl status wipi.service'"
        "alias wipi-start='sudo systemctl start wipi.service'"
        "alias wipi-stop='sudo systemctl stop wipi.service'"
        "alias wipi-restart='sudo systemctl restart wipi.service'"
        "alias wipi-logs='sudo journalctl -u wipi.service -f'"
        "alias wipi-config='sudo nano ${INSTALL_DIR}/wipi.py'"
    )
    
    # Path to .bash_aliases
    local bash_aliases="/home/pi/.bash_aliases"
    
    # Create .bash_aliases if it doesn't exist
    touch "$bash_aliases"
    
    # Check if WiPi aliases are already present
    if ! grep -q "# WiPi aliases" "$bash_aliases"; then
        log_info "Adding WiPi aliases to $bash_aliases"
        printf "\n%s\n" "${aliases[@]}" >> "$bash_aliases"
        
        # Set correct ownership
        chown pi:pi "$bash_aliases"
        
        # Notify user about new aliases
        log_info "Added the following aliases:"
        echo "  wipi-status  - Show WiPi service status"
        echo "  wipi-start   - Start WiPi service"
        echo "  wipi-stop    - Stop WiPi service"
        echo "  wipi-restart - Restart WiPi service"
        echo "  wipi-logs    - View WiPi service logs"
        echo "  wipi-config  - Edit WiPi configuration"
        echo ""
        log_info "To use these aliases in your current session, run: source ~/.bash_aliases"
    else
        log_info "WiPi aliases already exist in $bash_aliases"
    fi
}

# Add this function with the other functions
uninstall_wipi() {
    log_info "Starting WiPi uninstallation..."
    
    # Stop and disable the service
    log_info "Stopping and disabling WiPi service..."
    systemctl stop wipi.service
    systemctl disable wipi.service
    
    # Remove service file
    if [ -f "/etc/systemd/system/wipi.service" ]; then
        log_info "Removing WiPi service file..."
        rm "/etc/systemd/system/wipi.service"
        systemctl daemon-reload
    fi
    
    # Remove aliases from .bash_aliases
    log_info "Removing WiPi aliases..."
    local bash_aliases="/home/pi/.bash_aliases"
    if [ -f "$bash_aliases" ]; then
        # Create a temporary file without the WiPi aliases
        sed -i '/# WiPi aliases/,/^$/d' "$bash_aliases"
    fi
    
    # Ask about virtual environment
    if [ -d "$VENV_DIR" ]; then
        read -p "Do you want to remove the virtual environment at $VENV_DIR? (y/N): " remove_venv
        remove_venv=${remove_venv:-n}
        if [[ $remove_venv =~ ^[Yy]$ ]]; then
            log_info "Removing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            log_info "Keeping virtual environment"
        fi
    fi
    
    # Remove WiPi files
    if [ -d "$INSTALL_DIR" ]; then
        log_info "Removing WiPi files..."
        # Remove everything except the venv directory
        find "$INSTALL_DIR" -mindepth 1 ! -path "$VENV_DIR*" -delete
        
        # Remove install directory if empty and not containing venv
        if [ ! -d "$VENV_DIR" ] && [ -z "$(ls -A $INSTALL_DIR)" ]; then
            rmdir "$INSTALL_DIR"
        fi
    fi
    
    log_info "WiPi has been uninstalled"
    log_info "You may need to run 'source ~/.bash_aliases' to remove the aliases from your current session"
}

# Add this at the beginning of the main installation process, replacing the current header
echo -e "${GREEN}WiPi Management Tool${NC}"
echo "===================="
echo
echo "Please select an option:"
echo "1) Install/Reinstall WiPi (Auto WiFi/AP switching)"
echo "2) Uninstall WiPi (Remove service and files)"
echo "3) Modify WiPi Settings (Change SSID, password, timings)"
echo
read -p "Enter your choice [1-3]: " menu_choice

case $menu_choice in
    2)
        # Make sure VENV_DIR is set correctly before uninstalling
        if [ -f "${INSTALL_DIR}/wipi_service.py" ]; then
            # Try to get VENV_DIR from the existing service file
            VENV_DIR=$(grep -o 'VENV_DIR = "[^"]*"' "${INSTALL_DIR}/wipi_service.py" | cut -d'"' -f2)
        fi
        # If we couldn't find it, use the default
        if [ -z "$VENV_DIR" ]; then
            VENV_DIR="${INSTALL_DIR}/venv"
        fi
        uninstall_wipi
        exit 0
        ;;
    3)
        # Configure WiPi with advanced options
        if [ ! -f "${INSTALL_DIR}/wipi.py" ]; then
            log_error "WiPi is not installed. Please install it first."
            exit 1
        fi
        advanced_install
        exit 0
        ;;
    1|"")
        # Continue with normal installation
        log_info "Starting WiPi installation..."
        ;;
    *)
        log_error "Invalid option selected"
        exit 1
        ;;
esac

# First check and install system dependencies
log_info "Checking system dependencies..."
# Check for NetworkManager
if ! dpkg -l | grep -q "^ii.*network-manager"; then
    log_info "Installing NetworkManager..."
    apt-get update
    apt-get install -y network-manager
else
    log_info "NetworkManager is already installed"
fi

# Check for python3-venv
if ! dpkg -l | grep -q "^ii.*python3-venv"; then
    log_info "Installing python3-venv..."
    apt-get install -y python3-venv
else
    log_info "python3-venv is already installed"
fi

# Check for curl
if ! command -v curl &> /dev/null; then
    log_info "Installing curl..."
    apt-get install -y curl
else
    log_info "curl is already installed"
fi

# Download WiPi files
download_files

# Now set up the virtual environment
setup_venv

# Update the Python files with the correct venv path
update_python_files "$VENV_DIR"

# Then ask for installation type
echo "1) Basic Install (Default settings)"
echo "2) Advanced Install (Custom configuration)"
read -p "Select installation type [1/2]: " install_type

# Perform selected installation type
case $install_type in
    2)
        advanced_install
        ;;
    *)
        basic_install
        ;;
esac

# Add aliases
setup_aliases

# Final status check
if systemctl is-active --quiet wipi.service; then
    log_info "WiPi service is running successfully!"
else
    log_warn "Service may not have started properly. Please check status with:"
    log_warn "sudo systemctl status wipi.service"
fi

echo
log_info "Installation complete!"

# Add backup functionality
backup_config() {
    local backup_dir="${INSTALL_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
    log_info "Creating backup in ${backup_dir}"
    mkdir -p "${backup_dir}"
    
    if [ -f "${INSTALL_DIR}/wipi.py" ]; then
        cp "${INSTALL_DIR}/wipi.py" "${backup_dir}/"
    fi
    if [ -f "${INSTALL_DIR}/wipi_service.py" ]; then
        cp "${INSTALL_DIR}/wipi_service.py" "${backup_dir}/"
    fi
    
    log_info "Backup created successfully"
}

# Add to install_dependencies function
verify_networkmanager() {
    log_info "Verifying NetworkManager status..."
    if ! systemctl is-active --quiet NetworkManager; then
        log_info "Starting NetworkManager service..."
        systemctl start NetworkManager
        sleep 2
        if ! systemctl is-active --quiet NetworkManager; then
            log_error "Failed to start NetworkManager"
            exit 1
        fi
    fi
    log_info "NetworkManager is running"
}
