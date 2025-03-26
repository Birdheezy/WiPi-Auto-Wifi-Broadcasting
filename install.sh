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

# Virtual environment settings
VENV_DIR="${INSTALL_DIR}/venv"
PYTHON_BIN="/usr/bin/python3"

# Repository settings
GITHUB_RAW_URL="https://raw.githubusercontent.com/Birdheezy/WiPi-Auto-Wifi-Broadcasting/main"

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

# Define all helper functions first
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

check_repository_access() {
    log_info "Checking repository access..."
    if ! curl -s -f -I "${GITHUB_RAW_URL}/wipi.py" > /dev/null; then
        log_error "Cannot access repository at ${GITHUB_RAW_URL}"
        log_error "Please check your internet connection and repository URL"
        exit 1
    fi
    log_info "Repository is accessible"
}

setup_venv() {
    log_info "Virtual Environment Setup"
    echo "------------------------"
    read -p "Do you have an existing virtual environment you'd like to use? (y/N): " use_existing_venv
    use_existing_venv=${use_existing_venv:-n}

    if [[ $use_existing_venv =~ ^[Yy]$ ]]; then
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

    log_info "Upgrading pip..."
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip
    deactivate
}

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
    
    verify_networkmanager
}

download_files() {
    log_info "Downloading WiPi files..."
    
    check_repository_access
    
    if [ -f "${INSTALL_DIR}/wipi.py" ] || [ -f "${INSTALL_DIR}/wipi_service.py" ]; then
        backup_config
    fi
    
    local temp_dir
    temp_dir=$(mktemp -d) || {
        log_error "Failed to create temporary directory"
        exit 1
    }
    
    local files=("wipi.py" "wipi_service.py")
    for file in "${files[@]}"; do
        log_info "Downloading ${file}..."
        if ! curl -s -S -f -o "${temp_dir}/${file}" "${GITHUB_RAW_URL}/${file}"; then
            log_error "Failed to download ${file}"
            log_error "URL: ${GITHUB_RAW_URL}/${file}"
            rm -rf "${temp_dir}"
            exit 1
        fi
    done
    
    for file in "${files[@]}"; do
        if [ ! -s "${temp_dir}/${file}" ]; then
            log_error "Downloaded file ${file} is empty"
            rm -rf "${temp_dir}"
            exit 1
        fi
    done
    
    mkdir -p "$INSTALL_DIR" || {
        log_error "Failed to create installation directory"
        rm -rf "${temp_dir}"
        exit 1
    }
    
    cp "${temp_dir}"/* "$INSTALL_DIR/" || {
        log_error "Failed to copy files to installation directory"
        rm -rf "${temp_dir}"
        exit 1
    }
    
    rm -rf "${temp_dir}"
    
    chmod 755 "$INSTALL_DIR"/*.py || log_error "Failed to set file permissions"
    chown -R pi:pi "$INSTALL_DIR" || log_error "Failed to set file ownership"
    
    log_info "Files downloaded and installed successfully"
}

create_wipi_service() {
    log_info "Creating WiPi service..."
    cat > /etc/systemd/system/wipi.service << EOF
[Unit]
Description=WiPi Auto WiFi Broadcasting
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/wipi_service.py --daemon
Environment=PYTHONPATH=${INSTALL_DIR}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    chmod 644 /etc/systemd/system/wipi.service
}

configure_wipi() {
    local ssid=$1
    local password=$2
    local ip=$3
    local check_interval=$4
    local loop_interval=$5
    local debug=$6
    local open_ap=$7

    cp "${INSTALL_DIR}/wipi.py" "${INSTALL_DIR}/wipi.py.bak"

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

update_python_files() {
    local venv_path=$1
    sed -i "s|VENV_DIR = os.path.dirname(INSTALL_DIR)|VENV_DIR = \"${venv_path}\"|" "${INSTALL_DIR}/wipi_service.py"
}

setup_aliases() {
    log_info "Setting up WiPi command aliases..."
    
    local aliases=(
        "# WiPi aliases"
        "alias wipi-status='sudo systemctl status wipi.service'"
        "alias wipi-start='sudo systemctl start wipi.service'"
        "alias wipi-stop='sudo systemctl stop wipi.service'"
        "alias wipi-restart='sudo systemctl restart wipi.service'"
        "alias wipi-logs='sudo journalctl -u wipi.service -f'"
        "alias wipi-config='sudo nano ${INSTALL_DIR}/wipi.py'"
    )
    
    local bash_aliases="/home/pi/.bash_aliases"
    touch "$bash_aliases"
    
    if ! grep -q "# WiPi aliases" "$bash_aliases"; then
        log_info "Adding WiPi aliases to $bash_aliases"
        printf "\n%s\n" "${aliases[@]}" >> "$bash_aliases"
        chown pi:pi "$bash_aliases"
        
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

basic_install() {
    log_info "Performing basic installation with default settings..."
    create_wipi_service
    systemctl daemon-reload
    systemctl enable wipi.service
    systemctl start wipi.service
    log_info "Basic installation completed successfully!"
}

advanced_install() {
    log_info "Starting advanced installation..."
    
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
    
    configure_wipi "$ssid" "$password" "$ip" "$check_interval" "$loop_interval" "$debug" "$open_ap"
    create_wipi_service
    systemctl daemon-reload
    systemctl enable wipi.service
    systemctl start wipi.service
    
    log_info "Advanced installation completed successfully!"
}

uninstall_wipi() {
    log_info "Starting WiPi uninstallation..."
    
    systemctl stop wipi.service
    systemctl disable wipi.service
    
    if [ -f "/etc/systemd/system/wipi.service" ]; then
        rm "/etc/systemd/system/wipi.service"
        systemctl daemon-reload
    fi
    
    local bash_aliases="/home/pi/.bash_aliases"
    if [ -f "$bash_aliases" ]; then
        sed -i '/# WiPi aliases/,/^$/d' "$bash_aliases"
    fi
    
    if [ -d "$VENV_DIR" ]; then
        read -p "Do you want to remove the virtual environment at $VENV_DIR? (y/N): " remove_venv
        remove_venv=${remove_venv:-n}
        if [[ $remove_venv =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
        fi
    fi
    
    if [ -d "$INSTALL_DIR" ]; then
        find "$INSTALL_DIR" -mindepth 1 ! -path "$VENV_DIR*" -delete
        if [ ! -d "$VENV_DIR" ] && [ -z "$(ls -A $INSTALL_DIR)" ]; then
            rmdir "$INSTALL_DIR"
        fi
    fi
    
    log_info "WiPi has been uninstalled"
    log_info "You may need to run 'source ~/.bash_aliases' to remove the aliases from your current session"
}

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (use sudo)"
    exit 1
fi

# Main menu
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
        if [ -f "${INSTALL_DIR}/wipi_service.py" ]; then
            VENV_DIR=$(grep -o 'VENV_DIR = "[^"]*"' "${INSTALL_DIR}/wipi_service.py" | cut -d'"' -f2)
        fi
        if [ -z "$VENV_DIR" ]; then
            VENV_DIR="${INSTALL_DIR}/venv"
        fi
        uninstall_wipi
        exit 0
        ;;
    3)
        if [ ! -f "${INSTALL_DIR}/wipi.py" ]; then
            log_error "WiPi is not installed. Please install it first."
            exit 1
        fi
        advanced_install
        exit 0
        ;;
    1|"")
        log_info "Starting WiPi installation..."
        ;;
    *)
        log_error "Invalid option selected"
        exit 1
        ;;
esac

# Install dependencies
log_info "Checking system dependencies..."
if ! dpkg -l | grep -q "^ii.*network-manager"; then
    log_info "Installing NetworkManager..."
    apt-get update
    apt-get install -y network-manager
fi

if ! dpkg -l | grep -q "^ii.*python3-venv"; then
    log_info "Installing python3-venv..."
    apt-get install -y python3-venv
fi

if ! command -v curl &> /dev/null; then
    log_info "Installing curl..."
    apt-get install -y curl
fi

# Download and install
download_files
setup_venv
update_python_files "$VENV_DIR"

# Installation type
echo "1) Basic Install (Default settings)"
echo "2) Advanced Install (Custom configuration)"
read -p "Select installation type [1/2]: " install_type

case $install_type in
    2)
        advanced_install
        ;;
    *)
        basic_install
        ;;
esac

setup_aliases

if systemctl is-active --quiet wipi.service; then
    log_info "WiPi service is running successfully!"
else
    log_warn "Service may not have started properly. Please check status with:"
    log_warn "sudo systemctl status wipi.service"
fi

log_info "Installation complete!"
