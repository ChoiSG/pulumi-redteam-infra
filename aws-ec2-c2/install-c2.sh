#!/bin/bash

# Dependencies and Impacket 
apt update -y
apt install -y git curl python3-pip make binutils bison gcc zip proxychains4 pipx 

pipx install impacket 
pipx install git+https://github.com/ly4k/Certipy.git
pipx install git+https://github.com/sc0tfree/updog.git
pipx ensurepath 

# Set hostname to aws-c2-<privateip>-<publicip>
PRIVATE_IP=$(hostname -I | awk '{print $1}' | tr '.' '-')
PUBLIC_IP=$(curl -s http://ipinfo.io/ip | tr '.' '-')
hostnamectl set-hostname "aws-c2-${PRIVATE_IP}-${PUBLIC_IP}"

########################################################
### Default/PoC - Installing Sliver and modsliver.py ###
########################################################

# TODO: Implement your own C2 installation automation here! 

# echo "[*] Installing Sliver C2 framework..."

# # Dependencies
# apt install -y libprotobuf-dev protobuf-compiler golang-go

# # GVM 
# rm -rf /root/.gvm
# bash < <(curl -s -S -L https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer)
# source /root/.gvm/scripts/gvm
# gvm install go1.20.7 -B
# gvm use go1.20.7 --default
# source /root/.gvm/scripts/gvm

# # Protobuf Go plugins
# go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.27.1
# go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2.0

# # Clone Sliver repository
# echo "[*] Cloning Sliver repository..."
# cd /opt
# git clone https://github.com/BishopFox/sliver.git
# cd /opt/sliver
# git checkout tags/v1.5.43

# echo "[!] 1. Modify/Obfuscate sliver source code with modsliver.py before compilation. For modsliver.py, get it from you-know-where"
# echo "[!] 2. Malleable C2 with http-c2.json from you-know-where"
# echo "[!] 3. Compile with: cd /opt/sliver && make pb && make"

