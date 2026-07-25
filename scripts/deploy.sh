#!/usr/bin/env bash
# siphira.fluximpact.org — redeploy on the droplet after a push to main.
#
# The Tailwind build runs in GitHub Actions, not here: the 512MB box is already
# running seven other apps and has no headroom for a node toolchain. CI uploads
# the built CSS as siphira-dist.tgz (archive root "dist/") before invoking this
# script. A manual run with no tarball present falls back to building locally.
#
# Manual run:
#   ssh fluximpact@165.245.221.118 "bash /srv/siphira/scripts/deploy.sh"
set -euo pipefail

APP_DIR="/srv/siphira"
DIST_TGZ="$APP_DIR/siphira-dist.tgz"
PYTHON="$APP_DIR/venv/bin/python"
PIP="$APP_DIR/venv/bin/pip"
URL="https://siphira.fluximpact.org"

cd "$APP_DIR"

echo "==> [1/7] Pulling latest code"
git fetch --quiet origin main
git reset --hard --quiet origin/main

echo "==> [2/7] Python dependencies"
$PIP install -r requirements.txt -q

echo "==> [3/7] Front-end assets"
if [ -f "$DIST_TGZ" ]; then
    echo "    using CI-built assets"
    rm -rf static/dist
    mkdir -p static
    tar -xzf "$DIST_TGZ" -C static     # archive root is dist/ → static/dist
    rm -f "$DIST_TGZ"
else
    echo "    no CI tarball — building locally (manual deploy)"
    npm ci --silent && npm run build
fi
# Fail loudly rather than serving an unstyled page: a missing stylesheet still
# returns HTTP 200, so this is the only place it can be caught cheaply.
if [ ! -s static/dist/site.css ]; then
    echo "  ERROR: static/dist/site.css missing or empty — assets did not build/transfer." >&2
    exit 1
fi
echo "    site.css: $(wc -c < static/dist/site.css) bytes"

echo "==> [4/7] collectstatic + migrate + seed"
set -a && source .env && set +a
export DJANGO_SETTINGS_MODULE=config.settings.production
mkdir -p logs media og_cache
# --clear wipes STATIC_ROOT so stale hashed files from past builds don't pile up.
$PYTHON manage.py collectstatic --noinput --clear
$PYTHON manage.py migrate --noinput
$PYTHON manage.py seed_data
$PYTHON manage.py create_admin

echo "==> [5/7] Sync scheduled jobs"
# CRITICAL: `crontab <file>` REPLACES the user's entire crontab. This app runs
# as `fluximpact`, which already owns the Flux Lab jobs (site_health, analytics
# rollups). Installing a file wholesale here would silently delete those and
# take down monitoring for the main site.
#
# So instead we splice: everything between the markers below is ours, the rest
# is left exactly as-is. Idempotent, and safe on a shared user.
CRON_BEGIN="# >>> siphira (managed by scripts/deploy.sh) >>>"
CRON_END="# <<< siphira <<<"
CRON_JOB="15 0 * * * cd $APP_DIR && DJANGO_SETTINGS_MODULE=config.settings.production $PYTHON manage.py rollup_analytics --days 3 >> $APP_DIR/logs/cron.log 2>&1"

if command -v crontab >/dev/null 2>&1; then
    CURRENT=$(crontab -l 2>/dev/null || true)
    # Drop any previous siphira block, keep every other line untouched.
    PRESERVED=$(printf '%s\n' "$CURRENT" | sed "\|^${CRON_BEGIN}$|,\|^${CRON_END}$|d")
    if printf '%s\n%s\n%s\n%s\n' "$PRESERVED" "$CRON_BEGIN" "$CRON_JOB" "$CRON_END" \
        | sed '/^$/N;/^\n$/D' | crontab - 2>/dev/null; then
        echo "    siphira cron block synced ($(crontab -l 2>/dev/null | grep -vcE '^\s*(#|$)') total job(s) on this user)"
    else
        echo "    WARNING: could not write crontab — skipping (non-fatal)" >&2
    fi
else
    echo "    no crontab available — skipping"
fi

echo "==> [6/7] Restart Gunicorn"
# Try the privileged restart first, but never depend on root: if the app user
# lacks the systemctl grant, kill the master directly. Gunicorn runs AS this
# user and the unit's Restart=on-failure makes systemd relaunch it — a real
# restart, no root required.
restart_app() {
    if sudo -n systemctl restart siphira 2>/dev/null; then
        echo "    restarted via systemctl"
        return 0
    fi
    echo "    no systemctl grant — killing gunicorn master (systemd relaunches)"
    local oldpid newpid
    oldpid=$(systemctl show siphira -p MainPID --value 2>/dev/null || echo 0)
    kill -9 "$oldpid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        sleep 1
        newpid=$(systemctl show siphira -p MainPID --value 2>/dev/null || echo 0)
        if [ "$(systemctl is-active siphira 2>/dev/null)" = active ] \
           && [ -n "$newpid" ] && [ "$newpid" != "0" ] && [ "$newpid" != "$oldpid" ]; then
            echo "    relaunched (MainPID $oldpid -> $newpid)"
            return 0
        fi
    done
    echo "  ERROR: gunicorn did not come back. Check: journalctl -u siphira -n 50" >&2
    return 1
}
restart_app

echo "==> [7/7] Health check (up AND actually styled)"
sleep 2
HTTP_STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$URL")
if [[ "$HTTP_STATUS" != "200" ]]; then
    echo "  ERROR: site returned HTTP $HTTP_STATUS — check: journalctl -u siphira -n 50" >&2
    exit 1
fi

# HTTP 200 alone is NOT enough: an unstyled page returns 200 too. Verify the
# served HTML actually links a built stylesheet.
BODY=$(curl -s "$URL")
if ! echo "$BODY" | grep -qE '/static/[^"'"'"']*\.css'; then
    echo "  ERROR: no built stylesheet in prod HTML — the page is rendering UNSTYLED." >&2
    exit 1
fi
echo "    up and styled (HTTP 200, built CSS linked)"

echo ""
echo "Deploy complete: $URL"
