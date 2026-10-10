# vendor-extractor

A Python 3.11 project that crawls publicly visible B2B supplier listing pages for a category and city, stores them in SQLite, and exports vendor records to Excel.

## Features

- Public-only data collection without login bypasses
- robots.txt enforcement and disallowed-path skipping
- Playwright-based crawling with Chromium
- HTML caching keyed by URL hash
- SQLite queue + vendor store with deduplication
- Parser using JSON-LD/embedded JSON with selector fallback
- Excel export with filters and formatting
- CLI commands: crawl, parse, export, all

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configuration

Edit `config.yaml` before running:

```yaml
categories:
  cloth:
    url: "https://dir.indiamart.com/impcat/cloth.html"
  plastic_materials:
    url: "https://dir.indiamart.com/impcat/plastic-materials.html"
  packaging:
    url: "https://dir.indiamart.com/impcat/packaging.html"

city: "bengaluru"

crawling:
  max_pages: 10
  delay_min: 2
  delay_max: 5
  max_retries: 2
  backoff_factor: 2.0
```

## Usage

```bash
python -m src.main crawl
python -m src.main parse
python -m src.main export
python -m src.main all
```

## Notes

- Sites that show captchas, login walls, OTP verification, or contact-gating are treated as blocking conditions; the run stops with a clear log message.
- Hidden fields are stored as `hidden`.
- Missing fields are empty strings.
- A random 2-5 second delay is enforced between requests.

## Database

Schema:

- queue(url TEXT PRIMARY KEY, kind TEXT, status TEXT, last_fetched TEXT)
- vendors(source_url TEXT PRIMARY KEY, name, city, address, gst, contact_person, phone, phone_type, categories, source_site, scraped_at)

Reruns skip done URLs and upsert vendors on `source_url`; `gst` is also used as a dedupe key when present.
