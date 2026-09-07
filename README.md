# scrapperr

Scrapes active tenders from the PPRA e-PMS portal
(https://epms.ppra.gov.pk/public/tenders/active-tenders) and posts new ones
to a Facebook Page via the Graph API. Designed to run once a day (cron).

## How it works

1. `scraper.py` fetches the first N pages of the active tenders listing
   (newest tenders appear on page 1) and parses each row into a dict.
2. `storage.py` keeps a local SQLite DB (`data/tenders.db`) of tender
   numbers that have already been posted, so the same tender is never
   posted twice.
3. `main.py` scrapes, diffs against the DB, and posts only the new tenders
   to the configured Facebook Page, oldest-new first.
4. **First run is special**: since the DB starts empty, the first run would
   otherwise try to post every tender on the scraped pages at once. Instead,
   it just seeds the DB with what's currently on the site and posts nothing.
   From the next run onward, only genuinely new tenders get posted.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Getting a Facebook Page Access Token

You need a **long-lived Page Access Token** with `pages_manage_posts` and
`pages_read_engagement` permissions.

1. Go to https://developers.facebook.com/apps and create a new app
   (type: "Business").
2. In the app dashboard, add the **Facebook Login** and/or use
   **Graph API Explorer** (top-right tool at
   https://developers.facebook.com/tools/explorer/).
3. In Graph API Explorer: select your app, click "Get Token" ->
   "Get User Access Token", and check the `pages_manage_posts` and
   `pages_read_engagement` (and `pages_show_list`) permissions.
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
you're posting to a page you don't personally administer, or once you want
this to run indefinitely for other people's pages. For your own page while
you're listed as an admin/developer on the app, it generally works without
review while the app is in Development mode.

### Config (`.env`)

| Variable               | Meaning                                              |
|-------------------------|-------------------------------------------------------|
| `FB_PAGE_ID`            | Your Facebook Page's numeric ID                      |
| `FB_PAGE_ACCESS_TOKEN`  | Long-lived Page access token (see above)             |
| `PAGES_TO_SCRAPE`       | Listing pages to scrape per run (50 tenders/page)    |
| `MAX_POSTS_PER_RUN`     | Safety cap on posts per run                          |
| `POST_DELAY_SECONDS`    | Delay between consecutive FB posts                   |

## Usage

```bash
# Dry run: scrape and print what would be posted, without posting or touching the DB
python main.py --dry-run

# Real run
python main.py

# Override how many listing pages to scrape
python main.py --pages 3
```

## Scheduling

Once credentials are confirmed working, run this daily via cron, e.g.:

```
0 9 * * * cd /home/abubakar-khalid/scrapperr && .venv/bin/python main.py >> data/run.log 2>&1
```
