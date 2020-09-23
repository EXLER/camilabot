#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

# Check if user has superuser priviliges
if [[ "$EUID" -ne 0 ]]; then
    printf "[!] You need superuser privileges to install SuperCamila!\n"
    exit 1
fi

printf "[+] Installing dependencies...\n"
# Install dependencies
apt install -y \
    python3 \
    python3-pip \
    curl \
    ffmpeg

pip3 install -r requirements.txt

# Install Node.js and npm
curl -sL https://deb.nodesource.com/setup_12.x | sudo -E bash -
apt install -y nodejs

# Install pm2
npm install -g pm2

# Run SuperCamila
pm2 start ../pm2.config.json
pm2 startup
env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u $USER --hp /home/$USER
pm2 save
