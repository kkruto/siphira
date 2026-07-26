#!/usr/bin/env bash
# One-time provisioning for siphira.fluximpact.org on the shared droplet.
# Run ONCE as root:  sudo bash bootstrap.sh
#
# Safe to re-run: every step is guarded. It deliberately does NOT touch any
# other app on the box — no shared config is rewritten, and this host gets its
# OWN certificate rather than being added to the shared fluximpact.org SAN cert,
# so nothing the other sites depend on is ever modified.
set -euo pipefail

# `set -e` aborts silently — you get your prompt back with no clue which line
# died. That cost two debugging round-trips already (an unquoted SECRET_KEY,
# then a SIGPIPE in the token generator), so always say where and why.
trap 'rc=$?; echo "" >&2; echo "  ERROR: bootstrap failed at line $LINENO (exit $rc)." >&2; echo "         Re-running is safe — every step is guarded." >&2; exit $rc' ERR

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

echo "==> [1/9] Checking the port"
# The point of this check is to avoid colliding with a SIBLING app, not to
# insist on a clean slate. On any re-run — and this script is explicitly
# designed to be re-run — our own gunicorn is already listening here, which is
# success, not a conflict. Only a foreign occupant is a real error.
if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
    if systemctl is-active --quiet siphira 2>/dev/null; then
        echo "    :$PORT held by this app's own siphira.service (re-run) — continuing"
    else
        echo "  ERROR: port $PORT is in use, and it is NOT siphira. Pick a different" >&2
        echo "         port in scripts/siphira.service AND scripts/nginx-siphira.conf." >&2
        ss -ltnp 2>/dev/null | grep ":$PORT " >&2
        exit 1
    fi
else
    echo "    :$PORT is free"
fi

echo "==> [2/9] System packages"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip git curl >/dev/null

echo "==> [3/9] Code at $APP_DIR"
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

echo "==> [4/9] Virtualenv"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
fi
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> [5/9] Environment file"
# This file is consumed two ways — `source`d by shell scripts and parsed by
# django-environ — so every value is single-quoted. Django's own
# get_random_secret_key() draws from "!@#$%^&*(-_=+)", which the shell happily
# interprets as syntax; an unquoted key produces "syntax error near unexpected
# token". We therefore generate from an alphanumeric alphabet AND quote it.
# 64 alphanumeric characters is ~381 bits, well beyond Django's own default.
# Generated with Python's `secrets`, NOT `tr < /dev/urandom | head -c N`.
# That pipeline looks fine and is a silent trap under `set -euo pipefail`:
# head exits once it has N bytes, closing the pipe, tr dies of SIGPIPE, and
# pipefail surfaces exit 141 — so `set -e` aborts the whole script with no
# error message at all. Using the venv interpreter (built in step 4) rather
# than bare `python3` keeps this independent of what is on PATH.
gen_token() {
    "$APP_DIR/venv/bin/python" -c \
        "import secrets, string, sys
n = int(sys.argv[1])
print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n)))" \
        "${1:-32}"
}

if [ ! -f "$APP_DIR/.env" ]; then
    SECRET=$(gen_token 64)
    SALT=$(gen_token 32)
    ADMIN_PW=$(gen_token 20)
    cat > "$APP_DIR/.env" <<EOF
SECRET_KEY='$SECRET'
DEBUG='False'
SITE_DOMAIN='$DOMAIN'
ALLOWED_HOSTS='$DOMAIN,127.0.0.1,localhost'
ANALYTICS_SALT='$SALT'

# Admin login. To change: cd $APP_DIR && venv/bin/python manage.py changepassword siphira
ADMIN_USERNAME='siphira'
ADMIN_EMAIL='siphirawanjiku0@gmail.com'
ADMIN_PASSWORD='$ADMIN_PW'

# Keyless push alerts for new messages/comments. Subscribe to this topic in the
# ntfy app. Leave blank to disable notifications entirely.
NTFY_TOPIC=''
EOF
    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "    wrote $APP_DIR/.env"
else
    echo "    .env already exists — left untouched"
fi

# Fail here rather than three steps later with a cryptic shell error. An .env
# written by an older version of this script may hold unquoted values.
if ! ( set -a; . "$APP_DIR/.env" ) >/dev/null 2>&1; then
    echo "" >&2
    echo "  ERROR: $APP_DIR/.env is not valid shell — most likely an unquoted" >&2
    echo "         SECRET_KEY containing \$ & ( ) ! % characters." >&2
    echo "" >&2
    echo "         Fix by regenerating it:" >&2
    echo "             sudo rm $APP_DIR/.env && sudo bash $0" >&2
    exit 1
fi

echo "==> [6/9] Django setup"
cd "$APP_DIR"
sudo -u "$APP_USER" bash -c "set -a && source .env && set +a && \
    export DJANGO_SETTINGS_MODULE=config.settings.production && \
    venv/bin/python manage.py migrate --noinput && \
    venv/bin/python manage.py collectstatic --noinput && \
    venv/bin/python manage.py seed_data && \
    venv/bin/python manage.py create_admin"

echo "==> [7/9] systemd unit"
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
    # Disable the symlink FIRST. A broken file left in sites-enabled is worse
    # than a failed deploy: nginx keeps serving its in-memory config, so
    # everything looks fine until the next restart or reboot — at which point
    # nginx refuses to start and takes every site on the box down with it.
    rm -f /etc/nginx/sites-enabled/siphira
    echo "  ERROR: nginx config test failed — vhost disabled, other sites untouched:" >&2
    # `|| true` is essential: nginx -t exits non-zero here by definition, and
    # without it the ERR trap fires and aborts the script before the cleanup
    # below ever runs. That is exactly how the broken symlink survived once.
    nginx -t >&2 2>&1 || true
    systemctl reload nginx || true
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
