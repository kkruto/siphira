# Siphira John

**[siphira.fluximpact.org](https://siphira.fluximpact.org)** · Nairobi, Kenya

Personal site, blog, and admin backend for Siphira John — merchandiser, brand
ambassador, and founder. Everything on the public site is editable from the
admin; publishing never requires a deploy.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.0 · Python 3.12+ |
| Styling | Tailwind CSS 3 (built in CI) |
| Content | Markdown (`mistune`), stored in the database |
| Database | SQLite (WAL mode) |
| Production | Gunicorn + WhiteNoise + nginx |
| Host | Shared DigitalOcean droplet, port 8007 |
| Images | Pillow (per-post Open Graph cards) |

Deliberately lean: no React, no Vite, no Postgres. The droplet is 512MB and
already runs seven other apps, so this one holds a single Gunicorn worker at
roughly 55MB. There is no client-side framework — the two interactive pieces
(comment form, feedback widget) are about 60 lines of vanilla JS between them.

---

## Running locally

**Prerequisites:** Python 3.12+ · Node 20+

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
npm install

cp .env.example .env          # set SECRET_KEY (anything works locally)
python manage.py migrate
python manage.py seed_data    # idempotent — loads her real copy
python manage.py createsuperuser
```

Two terminals:

```bash
python manage.py runserver 8010    # Django
npm run dev                        # Tailwind watch
```

| URL | What |
|-----|------|
| `http://127.0.0.1:8010` | The site |
| `/studio/` | Dashboard: traffic, inbox, comment moderation |
| `/admin/` | Django admin — writing and editing |

---

## Managing content

Everything is managed at `/admin/`; `/studio/` is the day-to-day view.

| Section | Controls |
|---------|---------|
| **Site settings** | Home/about copy, portrait, CV, email, social links, and the switches for comments and feedback. Singleton — edit, never add. |
| **Posts** | Blog. Markdown body with a live preview panel. Drafts stay private until published; `/drafts/<slug>/` previews one exactly as it will look live. |
| **Projects** | Name, status, and four separate Markdown fields — problem, approach, progress, lessons. Any left blank simply doesn't render. Plus dated updates and screenshots. |
| **Now entries** | The `/now/` page, grouped into building / learning / reading / focused on. |
| **Skill groups** | The four groups on `/skills/`. |
| **Comments** | Every comment is held for approval. Nothing appears publicly until approved. |
| **Contact messages** | Read-only inbox; the friendlier view is `/studio/inbox/`. |

Each post automatically gets a branded Open Graph card at
`/blog/<slug>/og.png`, so shared links don't all preview identically.

---

## Analytics

First-party, cookieless, and no third-party scripts — no Google Analytics, no
pixels. What is recorded per page view: path, referring host, device class,
and timestamp.

**Raw IP addresses are never stored.** The IP is combined with the user-agent
and a secret salt, hashed, and only a 32-character digest is kept, so repeat
visits within a day can be counted once. The current date is part of the
digest, so the hash changes at midnight and cannot be used to follow someone
over time.

Excluded from counting: bots (broad user-agent match), non-HTML requests, and
Siphira's own logged-in traffic.

`manage.py rollup_analytics` collapses raw views into `DailyStat` rows and
deletes raw views older than 90 days. Deploy splices it into the crontab at
00:15 daily.

`/privacy/` states all of this in plain language. **If you change what is
collected, change that page too.**

---

## Deployment

```
push to main → GitHub Actions builds Tailwind on the runner
             → scp the CSS bundle to the droplet
             → ssh runs scripts/deploy.sh (pip · collectstatic · migrate ·
               seed · cron · restart · health check)
```

`scripts/deploy.sh` fails the deploy if the served page isn't actually styled —
an unstyled page still returns HTTP 200, so status alone proves nothing. It
restarts via `systemctl` when the sudo grant exists and falls back to killing
the Gunicorn master (systemd relaunches it) when it doesn't, so deploys never
depend on root.

**Cron safety:** this app runs as the shared `fluximpact` user, which already
owns Flux Lab's cron jobs. `crontab <file>` *replaces* the whole crontab, so
deploy.sh splices its job into a marked block instead — Flux Lab's monitoring
survives every deploy. See `scripts/crontab.siphira`.

### First-time provisioning

Requires root on the droplet, once:

```bash
sudo bash scripts/bootstrap.sh
```

It checks port 8007 is free, clones the repo, builds the venv, generates
`.env` (with a random `SECRET_KEY`, analytics salt, and admin password),
installs the systemd unit, and configures nginx.

**TLS:** the vhost reuses the `fluximpact.org` certificate. Bootstrap verifies
that cert actually covers `siphira.fluximpact.org` — via a `*.fluximpact.org`
wildcard or an explicit SAN — and if it doesn't, it installs the vhost but
leaves it **disabled** rather than serving a browser warning, printing the
`certbot --expand` command to run deliberately. Expanding rewrites a
certificate eight sites share, so it is never done as a deploy side effect.

### Required GitHub secrets

| Secret | Value |
|--------|-------|
| `DROPLET_HOST` | The droplet IP |
| `DROPLET_SSH_KEY` | Private key for the `fluximpact` user |

---

## Project structure

```
siphira/
├── apps/site/                  # One app — the whole site
│   ├── models.py               #   SiteSettings, Post, Project, Comment,
│   │                           #   ContactMessage, Feedback, PageView, DailyStat
│   ├── views.py                #   Public pages + form endpoints + feeds
│   ├── studio.py               #   /studio/ — dashboard, inbox, moderation
│   ├── middleware.py           #   Cookieless analytics recorder
│   ├── og.py                   #   Pillow Open Graph cards
│   ├── notify.py               #   ntfy.sh push (SMTP is blocked on the box)
│   ├── markdown.py             #   mistune wrapper, raw HTML disabled
│   └── management/commands/    #   seed_data · rollup_analytics · create_admin
├── config/settings/            # base · development · production
├── scripts/                    # deploy.sh · bootstrap.sh · systemd · nginx
├── static/src/tailwind.css     # → built to static/dist/site.css
└── .github/workflows/deploy.yml
```

---

## Design tokens

From Siphira's brief, in `tailwind.config.js`:

| Token | Hex | Used for |
|-------|-----|---------|
| `paper` | `#FAFAF9` | Page background (warm white) |
| `ink` | `#1F2937` | Headings and body text (charcoal) |
| `sage` | `#84A98C` | Buttons, accents, links |
| `sand` | `#D6C6B8` | Cards and highlights |

Typeface is Nunito — rounded, modern sans. Generous whitespace, rounded
corners, and subtle fade-in-on-scroll, all of which respect
`prefers-reduced-motion`.

---

## Security

- `django-axes` locks out brute-force admin logins (5 attempts, 1h cooloff)
- Rate limiting on every write endpoint: contact 5/min, comments 3/min, plus
  daily caps
- Honeypot fields on both public forms — bots get a 200 so they don't retry
- Comments approval-gated by default; commenter emails never rendered publicly
- CSRF, HSTS, nosniff, `X-Frame-Options: DENY`, secure cookies in production
- Markdown rendered with raw HTML escaped
