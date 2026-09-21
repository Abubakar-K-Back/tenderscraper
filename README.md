# scrapperr

Scrapes active tenders from the PPRA e-PMS portal with official filters
(https://epms.ppra.gov.pk/public/tenders/active-tenders), then posts
**sector digests + one spotlight** to a Facebook Page via the Graph API.

## Filters (locked in `config.py`)

| Filter | Values |
|--------|--------|
| `tender_type` | `1` (Tender Notice) |
| Procurement category | Goods (`1`), Works (`2`), Non-consultancy Services (`4`) |
| Sector | Civil Works (`6`), Health/Medicines (`13`), Info and Comm Tech (`14`) |
| City | Islamabad, Lahore, Karachi |

Each category × sector × city combo is requested separately (PPRA accepts one
value per field). Results are deduped by tender number.

## How it works

1. `scraper.py` fetches filtered listing pages and parses each row.
2. `storage.py` keeps `data/tenders.db` so the same tender is never posted twice.
3. `main.py` diffs against the DB, fetches detail pages, then:
   - groups new tenders by **sector** (`niches.py`)
   - posts up to `MAX_DIGEST_POSTS_PER_DAY` digest images + captions
   - posts **one spotlight** single-tender card
   - waits `POST_DELAY_SECONDS` between posts
4. **First run** seeds the DB with current filtered listings and posts nothing.

### What we scrape from the detail page (for posts)

Used: Organization Name, City, Procurement Category, Sector, Status,
Closing Date & Time, Bid Security, Bid Validity, Procurement Procedure,
title, detail URL.

Skipped on the Page (noise): full office address, corrigendum history body,
workflow type, contact phone.

## Project layout

| File                 | Purpose                                                |
|-----------------------|---------------------------------------------------------|
| `scraper.py`          | Filtered listing + detail fetch/parse                   |
| `storage.py`           | SQLite dedup tracking                                   |
| `niches.py`            | Sector digests + spotlight scoring                      |
| `facebook_poster.py`   | Digest/spotlight captions, TinyURL, Graph API posts     |
| `image_generator.py`   | Digest list cards + single-tender spotlight images      |
| `main.py`              | Orchestrates scrape → group → digest → spotlight        |
| `scheduler.py`         | Runs `main.run()` once a day inside the Docker container |
| `config.py`            | Reads `.env` / filter defaults                          |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Image generation needs the DejaVu fonts (`fonts-dejavu-core`) for text
rendering. The Dockerfile installs this automatically; if running outside
Docker on a minimal Linux box, install it yourself (`apt-get install
fonts-dejavu-core`) — most desktop Linux distros already have it.

### Getting a Facebook Page Access Token

You need a **long-lived Page Access Token** with `pages_manage_posts` and
`pages_read_engagement` permissions.

1. Go to https://developers.facebook.com/apps and create a new app
   (type: "Business").
2. In the app dashboard, add the **Facebook Login** and/or use
   **Graph API Explorer** (top-right tool at
   https://developers.facebook.com/tools/explorer/).
3. In Graph API Explorer: select your app, click "Get Token" ->
   "Get User Access Token", and check the `pages_manage_posts`,
   `pages_read_engagement` and `pages_show_list` permissions. If they
   don't appear in the search list, first add them under your app's
   dashboard → **Use cases** → "Manage everything on your Page" → each
   permission's **Add** button.
4. Exchange that short-lived **user** token for a long-lived one:
   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-user-token}
   ```
5. Use the long-lived user token to fetch your **Page** access token
   (this one does not expire as long as the user token/session stays valid):
   ```
   GET https://graph.facebook.com/v21.0/me/accounts
     ?access_token={long-lived-user-token}
   ```
   This returns a list of pages you manage, each with its own `access_token`
   and `id` — that's your `FB_PAGE_ID` and `FB_PAGE_ACCESS_TOKEN`.
6. Put those values in `.env`.

Note: your Facebook app will need App Review for `pages_manage_posts` if
you're posting to a page you don't personally administer. For your own
page while you're listed as an admin/developer on the app, it generally
works without review while the app is in Development mode.

### Config (`.env`)

| Variable                   | Meaning                                              |
|-----------------------------|-------------------------------------------------------|
| `FB_PAGE_ID`                | Your Facebook Page's numeric ID                      |
| `FB_PAGE_ACCESS_TOKEN`      | Long-lived Page access token (see above)             |
| `PAGES_TO_SCRAPE`           | Pages per category×sector×city combo                 |
| `TENDER_TYPE`               | PPRA tender type (`1` = Tender Notice)               |
| `CITIES`                    | Comma-separated city names                           |
| `ENABLED_NICHES`            | Digest niches: `civil_works,health,ict`              |
| `MAX_DIGEST_POSTS_PER_DAY`  | Max sector digest posts per run (default 3)          |
| `DIGEST_MAX_ITEMS`          | Rows on the digest image (caption lists all)         |
| `SPOTLIGHT_ENABLED`         | `true`/`false` — one shareable single-tender card    |
| `POST_DELAY_SECONDS`        | Delay between FB posts (default 3600 = 1 hour)       |
| `RUN_TIME`                  | Daily run time, `HH:MM` container-local time (Docker)|

Procurement categories and sectors are fixed in `config.py` (Goods/Works/
Non-consultancy Services × Civil Works/Health/ICT). Change them there if you
expand the shortlist.

> **Why digests + one spotlight?** Facebook suppresses Pages that blast many
> near-identical API photos. A few useful sector digests plus one spotlight
> card look like a real alert page and invite comments/shares. Getting real
> followers still matters for distribution.

## Usage

```bash
# Dry run: scrape, generate preview images (data/preview_<tender_no>.png),
# print what would be posted — no posting, no DB writes
python main.py --dry-run

# Real run
python main.py

# Override how many listing pages to scrape
python main.py --pages 3
```

## Running with Docker (recommended)

```bash
cp .env.example .env   # fill in FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN

# Start the self-scheduling container (runs daily at RUN_TIME, default 09:00
# Asia/Karachi time; keeps running in the background)
docker compose up -d

docker compose logs -f     # watch it
docker compose down        # stop it

# After changing any code, rebuild before running again —
# `docker compose run`/`up` does NOT auto-rebuild on its own:
docker compose build

# One-off manual runs
docker compose run --rm tender-poster python main.py --dry-run
docker compose run --rm tender-poster python main.py
```

The SQLite dedup DB is bind-mounted to `./data/tenders.db` on the host, so it
persists across container rebuilds/restarts. Credentials come from `.env` via
`env_file` in `docker-compose.yml` — they are never baked into the image.

## Scheduling (without Docker)

If you'd rather not use Docker, run this daily via cron instead:

```
0 9 * * * cd /home/abubakar-khalid/scrapperr && .venv/bin/python main.py >> data/run.log 2>&1
```
