# scrapperr

Scrapes active tenders from the PPRA e-PMS portal with official filters
(https://epms.ppra.gov.pk/public/tenders/active-tenders), then posts
**sector digests** to a Facebook Page via the Graph API.

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
   - skips generic/short titles (e.g. "Invitation to Bid")
   - groups new tenders by **sector** (`niches.py`)
   - posts up to `MAX_DIGEST_POSTS_PER_DAY` digests (**largest niche first**)
   - image shows `DIGEST_MAX_ITEMS` cards; caption lists up to `DIGEST_CAPTION_MAX`
   - waits `POST_DELAY_SECONDS` between posts
4. **First run** seeds the DB with current filtered listings and posts nothing.

## Project layout

| File                 | Purpose                                                |
|-----------------------|---------------------------------------------------------|
| `scraper.py`          | Filtered listing + detail fetch/parse                   |
| `storage.py`           | SQLite dedup tracking                                   |
| `niches.py`            | Sector grouping + title quality filter                  |
| `facebook_poster.py`   | Digest captions + Graph API feed posts                  |
| `image_generator.py`   | Digest list cards (rotating themes)                     |
| `main.py`              | Orchestrates scrape → group → digest posts              |
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
| `DIGEST_MAX_ITEMS`          | Cards on the digest image (default 4)                |
| `DIGEST_CAPTION_MAX`        | Max tenders listed in caption (default 10)           |
| `POST_DELAY_SECONDS`        | Delay between FB posts (e.g. 28800 = 8 hours)        |
| `RUN_TIME`                  | Daily run time, `HH:MM` container-local time (Docker)|

Procurement categories and sectors are fixed in `config.py`.

## Usage

```bash
python main.py --dry-run
python main.py
python main.py --pages 3
```

## Running with Docker (recommended)

```bash
cp .env.example .env   # fill in FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN
docker compose up -d
docker compose logs -f
docker compose down
docker compose build   # after code changes
docker compose run --rm tender-poster python main.py --dry-run
docker compose run --rm tender-poster python main.py
```

The SQLite dedup DB is bind-mounted to `./data/tenders.db`. Credentials come
from `.env` via `env_file` in `docker-compose.yml`.

## Scheduling (without Docker)

```
0 9 * * * cd /path/to/tenderscraper && .venv/bin/python main.py >> data/run.log 2>&1
```
