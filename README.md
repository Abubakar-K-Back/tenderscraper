# scrapperr

Scrapes active tenders from the PPRA e-PMS portal
(https://epms.ppra.gov.pk/public/tenders/active-tenders) and posts new ones
as branded image posts to a Facebook Page via the Graph API. Designed to
run once a day, spaced out over the day rather than all at once.

## How it works

1. `scraper.py` fetches the first N listing pages (newest tenders appear on
   page 1) and parses each row into a dict.
2. `storage.py` keeps a local SQLite DB (`data/tenders.db`) of tender
   numbers already posted, so the same tender is never posted twice.
3. `main.py` scrapes, diffs against the DB, and for each new tender:
   - fetches that tender's detail page (`scraper.fetch_tender_detail`) for
     fields not on the listing page (Bid Security, Bid Validity, Bidding
     Method, Procurement Category, ...)
   - generates a branded image card (`image_generator.py`, via Pillow):
     Project title, Department, Submission Deadline, Bid Security, Bid
     Validity, and a Category pill — nothing else
   - posts the image to the Facebook Page's `/photos` endpoint, with a
     formal text notice (`facebook_poster.format_tender_message`) as the
     caption
   - waits `POST_DELAY_SECONDS` before the next one
4. **First run is special**: since the DB starts empty, the first run would
   otherwise try to post every scraped tender at once. Instead, it just
   seeds the DB with what's currently on the site and posts nothing. From
   the next run onward, only genuinely new tenders get posted.

## Project layout

| File                 | Purpose                                                |
|-----------------------|---------------------------------------------------------|
| `scraper.py`          | Fetches/parses the listing pages and tender detail pages |
| `storage.py`           | SQLite dedup tracking                                   |
| `facebook_poster.py`   | Builds the caption text, shortens links, posts to FB    |
| `image_generator.py`   | Renders the branded tender image (Pillow)               |
| `main.py`              | Orchestrates scrape → diff → generate → post            |
| `scheduler.py`         | Runs `main.run()` once a day inside the Docker container |
| `config.py`            | Reads `.env` / defaults                                 |

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

| Variable               | Meaning                                              |
|-------------------------|-------------------------------------------------------|
| `FB_PAGE_ID`            | Your Facebook Page's numeric ID                      |
| `FB_PAGE_ACCESS_TOKEN`  | Long-lived Page access token (see above)             |
| `PAGES_TO_SCRAPE`       | Listing pages to scrape per run (50 tenders/page)    |
| `MAX_POSTS_PER_RUN`     | Safety cap on posts per run                          |
| `POST_DELAY_SECONDS`    | Delay between consecutive FB posts (default: 1200 = 20 min) |
| `RUN_TIME`              | Daily run time, `HH:MM` container-local time (Docker scheduler only) |

> **Why the 20-minute delay?** A brand-new Page with no followers can get
> its posts silently hidden by Facebook's spam/integrity system if you
> publish many near-identical items in quick succession. Spacing posts
> minutes apart looks far more natural, and fits a "tender alert" page
> better than a burst-post anyway.
>
> More generally: a brand-new, zero-follower Page posting only via API can
> have its posts suppressed from the public feed even while Facebook's own
> API reports them as `is_published: true`. Getting a handful of real
> people to like/follow the Page is the actual fix — not a code change.

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
