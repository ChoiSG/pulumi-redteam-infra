#!/bin/bash
echo "[*] Starting redirector setup..."

# Dependencies
sudo apt update -y 
sudo apt install -y nginx certbot python3-pip git
sudo pip3 install certbot-dns-multi --break-system-packages

# Obtain SSL certificate based on DNS provider
echo "[*] Obtaining SSL certificate using DNS provider: $DNS_PROVIDER"
sudo mkdir -p /etc/letsencrypt

if [ "$DNS_PROVIDER" = "cloudflare" ]; then
    sudo bash -c "cat > /etc/letsencrypt/dns-multi.ini << EOF
dns_multi_provider = cloudflare
CLOUDFLARE_DNS_API_TOKEN = $CLOUDFLARE_API_TOKEN
EOF"zz

elif [ "$DNS_PROVIDER" = "route53" ]; then
    sudo bash -c "cat > /etc/letsencrypt/dns-multi.ini << EOF
dns_multi_provider = route53
AWS_HOSTED_ZONE_ID = $AWS_ROUTE53_ZONE_ID
AWS_ACCESS_KEY_ID = $AWS_ACCESS_KEY
AWS_SECRET_ACCESS_KEY = $AWS_SECRET_KEY
AWS_REGION = $AWS_REGION
EOF"

else
    echo "[!] Error: DNS_PROVIDER must be either 'cloudflare' or 'route53'"
    exit 1
fi

sudo chmod 600 /etc/letsencrypt/dns-multi.ini

# Obtain wildcard certificate 
sudo certbot certonly \
  --authenticator dns-multi \
  --dns-multi-credentials /etc/letsencrypt/dns-multi.ini \
  --server https://acme-v02.api.letsencrypt.org/directory \
  -d "*.$DOMAIN" -d "$DOMAIN" \
  --agree-tos \
  --non-interactive \
  --email "admin@$DOMAIN"

echo "[*] SSL certificate obtained successfully"

# Install nginx configuration (should already be at /etc/nginx/nginx.conf)
sudo chown -R www-data:www-data /var/www/html
sudo chmod -R 755 /var/www/html
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

# Set hostname to aws-c2-<privateip>-<publicip>
PRIVATE_IP=$(hostname -I | awk '{print $1}' | tr '.' '-')
PUBLIC_IP=$(curl -s http://ipinfo.io/ip | tr '.' '-')
hostnamectl set-hostname "aws-c2-${PRIVATE_IP}-${PUBLIC_IP}"

echo "[*] Redirector setup complete!"
