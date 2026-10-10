import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class CategoryCrawler:
    def __init__(self, fetch_manager, db, city: str, max_pages: int = 10):
        self.fetch_manager = fetch_manager
        self.db = db
        self.city = city
        self.max_pages = max_pages

    def crawl_category(self, category_url: str) -> int:
        logger.info("Crawling category: %s", category_url)
        self.db.queue_url(category_url, "category")

        collected = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(category_url, wait_until="domcontentloaded", timeout=30000)
                if self._detect_blocking_wall(page):
                    logger.error("Login or captcha wall detected for %s", category_url)
                    self.db.mark_failed(category_url, "login_wall_detected")
                    return 0

                loaded_count = self._count_profiles(page)
                page_index = 0

                while page_index < self.max_pages:
                    button = page.query_selector(
                        "button:has-text('Load More'), a:has-text('Load More'), a:has-text('Show More')"
                    )
                    if not button:
                        break

                    button.click()
                    page.wait_for_timeout(2000)
                    page_index += 1
                    new_count = self._count_profiles(page)
                    if new_count <= loaded_count:
                        break
                    loaded_count = new_count

                html = page.content()
                profile_urls = self._extract_profile_urls(html, category_url)
                for url in profile_urls:
                    if self.db.queue_url(url, "profile"):
                        collected += 1

                self.db.mark_done(category_url)
            except Exception as exc:
                logger.error("Error while crawling %s: %s", category_url, exc)
                self.db.mark_failed(category_url, str(exc))
            finally:
                browser.close()

        return collected

    def _detect_blocking_wall(self, page) -> bool:
        page_text = page.content().lower()
        blocked = [
            "login",
            "sign in",
            "otp",
            "captcha",
            "recaptcha",
            "verify your account",
            "view contact no",
        ]
        return any(token in page_text for token in blocked)

    def _count_profiles(self, page) -> int:
        selectors = [
            ".product-item",
            ".company-card",
            ".vendor-listing",
            "[data-company-id]",
            "a.company-link",
        ]
        for selector in selectors:
            elements = page.query_selector_all(selector)
            if elements:
                return len(elements)
        return 0

    def _extract_profile_urls(self, html: str, base_url: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        urls = set()
        selectors = [
            "a.company-link",
            "a[href*='/supplier/']",
            "a[href*='/company/']",
            "a[href*='/vendor/']",
            ".product-item a",
            ".company-card a",
        ]
        for selector in selectors:
            for link in soup.select(selector):
                href = link.get("href", "")
                if not href:
                    continue
                full_url = urljoin(base_url, href)
                if any(token in full_url for token in ["/supplier/", "/company/", "/vendor/"]):
                    urls.add(full_url)
        return list(urls)
