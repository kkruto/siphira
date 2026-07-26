#!/usr/bin/env bash
# One-time provisioning for siphira.fluximpact.org on the shared droplet.
# Run ONCE as root:  sudo bash bootstrap.sh
#
# Safe to re-run: every step is guarded. It deliberately does NOT touch any
# other app on the box — no shared config is rewritten, no certificate is
# renewed or expanded (see the TLS check at the end, which reports rather than
# acts, because expanding the cert rewrites what all eight sites share).
set -euo pipefail

APP_USER="fluximpact"          # reuse the fleet user so /_status/ can see this app
APP_DIR="/srv/siphira"
REPO="https://github.com/kkruto/siphira.git"
DOMAIN="siphira.fluximpact.org"
PORT=8007
# Let's Encrypt expiry notices go here. Ken's address, not Siphira's — she is
# not the one who fixes a failed renewal at 2am.
CERT_EMAIL="kkimtai@gmail.com"

if [ "$EUID" -ne 0 ]; then
    echo "Run as root: sudo bash $0" >&2
    exit 1
fi

echo "==> [1/8] Checking the port is free"
if ss -ltnp 2>/dev/null | grep -q ":$PORT "; then
    echo "  ERROR: port $PORT is already in use by another app. Pick a different" >&2
    echo "         port in scripts/siphira.service AND scripts/nginx-siphira.conf." >&2
    ss -ltnp | grep ":$PORT " >&2
    exit 1
fi
echo "    :$PORT is free"

echo "==> [2/8] System packages"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip git curl >/dev/null

echo "==> [3/8] Code at $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
    echo "    repo already present — pulling"
    sudo -u "$APP_USER" git -C "$APP_DIR" fetch --quiet origin main
    sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard --quiet origin/main
else
    mkdir -p "$APP_DIR"
    chown "$APP_USER:$APP_USER" "$APP_DIR"
    sudo -u "$APP_USER" git clone --quiet "$REPO" "$APP_DIR"
fi
mkdir -p "$APP_DIR"/{logs,media,og_cache,static/dist}
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
# nginx (www-data) serves /media/ via alias, so it must be able to traverse
# into the app directory. Note this is why the app lives under /srv and not in
# /home/fluximpact, which is mode 750 and blocks www-data entirely.
chmod 755 "$APP_DIR" "$APP_DIR/media"

echo "==> [4/8] Virtualenv"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
fi
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> [5/8] Environment file"
if [ ! -f "$APP_DIR/.env" ]; then
    SECRET=$(sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -c \
        "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    SALT=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32)
    cat > "$APP_DIR/.env" <<EOF
SECRET_KEY=$SECRET
DEBUG=False
SITE_DOMAIN=$DOMAIN
ALLOWED_HOSTS=$DOMAIN,127.0.0.1,localhost
ANALYTICS_SALT=$SALT

# Admin login. CHANGE ADMIN_PASSWORD, then re-run with ADMIN_PASSWORD_RESET=1
# to apply it, or use: venv/bin/python manage.py changepassword siphira
ADMIN_USERNAME=siphira
ADMIN_EMAIL=siphirawanjiku0@gmail.com
ADMIN_PASSWORD=$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)

# Keyless push alerts for new messages/comments. Subscribe to this topic in the
# ntfy app. Leave blank to disable notifications entirely.
NTFY_TOPIC=
EOF
    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "    wrote $APP_DIR/.env (admin password generated — see below)"
else
    echo "    .env already exists — left untouched"
fi

echo "==> [6/8] Django setup"
cd "$APP_DIR"
sudo -u "$APP_USER" bash -c "set -a && source .env && set +a && \
    export DJANGO_SETTINGS_MODULE=config.settings.production && \
    venv/bin/python manage.py migrate --noinput && \
    venv/bin/python manage.py collectstatic --noinput && \
    venv/bin/python manage.py seed_data && \
    venv/bin/python manage.py create_admin"

echo "==> [7/8] systemd unit"
cp "$APP_DIR/scripts/siphira.service" /etc/systemd/system/siphira.service
systemctl daemon-reload
systemctl enable --now siphira
sleep 3
if [ "$(systemctl is-active siphira)" != "active" ]; then
    echo "  ERROR: service failed to start. journalctl -u siphira -n 40" >&2
    journalctl -u siphira -n 40 --no-pager >&2
    exit 1
fi
echo "    siphira.service active on :$PORT"

echo "==> [8/9] nginx (HTTP) + TLS certificate"
# This host gets its OWN certificate rather than being added to the shared
# fluximpact.org SAN cert. `certbot --expand` would rewrite the certificate
# that 11 other names depend on; a separate cert is the same outcome with no
# blast radius, and it renews on its own schedule.
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

if [ -d "$CERT_DIR" ]; then
    echo "    certificate for $DOMAIN already exists — reusing"
else
    # Ordering matters: the TLS vhost references a cert that does not exist
    # yet, and `nginx -t` fails hard on a missing certificate file. So serve
    # HTTP first, get the cert, then swap.
    echo "    installing temporary HTTP vhost for the ACME challenge"
    mkdir -p /var/www/certbot
    cp "$APP_DIR/scripts/nginx-siphira-http.conf" /etc/nginx/sites-available/siphira
    ln -sf /etc/nginx/sites-available/siphira /etc/nginx/sites-enabled/siphira
    if ! nginx -t 2>/dev/null; then
        echo "  ERROR: nginx rejected the temporary HTTP vhost:" >&2
        nginx -t >&2
        rm -f /etc/nginx/sites-enabled/siphira
        exit 1
    fi
    systemctl reload nginx

    echo "    requesting certificate for $DOMAIN (webroot ACME)"
    if ! certbot certonly --webroot -w /var/www/certbot \
            -d "$DOMAIN" \
            --non-interactive --agree-tos \
            --email "$CERT_EMAIL" \
            --cert-name "$DOMAIN"; then
        echo "" >&2
        echo "  ERROR: certificate issuance failed. The site is NOT enabled." >&2
        echo "         The temporary HTTP vhost has been removed so nothing" >&2
        echo "         serves this host unencrypted." >&2
        echo "         Check DNS resolves to this box and port 80 is reachable." >&2
        rm -f /etc/nginx/sites-enabled/siphira
        nginx -t >/dev/null 2>&1 && systemctl reload nginx
        exit 1
    fi
fi

echo "==> [9/9] nginx (TLS)"
cp "$APP_DIR/scripts/nginx-siphira.conf" /etc/nginx/sites-available/siphira
ln -sf /etc/nginx/sites-available/siphira /etc/nginx/sites-enabled/siphira
if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "    nginx reloaded — $DOMAIN served over TLS with its own certificate"
else
    echo "  ERROR: nginx config test failed — rolling back to no vhost:" >&2
    nginx -t >&2
    rm -f /etc/nginx/sites-enabled/siphira
    systemctl reload nginx
    exit 1
fi

echo ""
echo "──────────────────────────────────────────────────────────────"
echo "Bootstrap complete."
echo "  Service : systemctl status siphira"
echo "  Logs    : journalctl -u siphira -f   |   tail -f $APP_DIR/logs/app.log"
echo "  Admin   : https://$DOMAIN/admin/"
echo "  Studio  : https://$DOMAIN/studio/"
echo ""
echo "  Admin credentials are in $APP_DIR/.env — read them, then change the"
echo "  password:  cd $APP_DIR && venv/bin/python manage.py changepassword siphira"
echo "──────────────────────────────────────────────────────────────"
