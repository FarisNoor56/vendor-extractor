import hashlib
import os
import random
import time
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright


class FetchManager:
    def __init__(
        self,
        html_cache_dir: str,
        delay_min: float = 2,
        delay_max: float = 5,
        max_retries: int = 2,
        backoff_factor: float = 2.0,
    ):
        self.html_cache_dir = html_cache_dir
        os.makedirs(html_cache_dir, exist_ok=True)
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def _cache_path(self, url: str) -> str:
        digest = hashlib.md5(url.encode("utf-8")).hexdigest()
        return os.path.join(self.html_cache_dir, f"{digest}.html")

    def _is_cached(self, url: str) -> bool:
        return os.path.exists(self._cache_path(url))

    def _read_cache(self, url: str) -> Optional[str]:
        path = self._cache_path(url)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def _write_cache(self, url: str, html: str):
        path = self._cache_path(url)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)

    def _sleep_between_requests(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def check_robots_txt(self, url: str) -> dict:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            self._sleep_between_requests()
            response = requests.get(robots_url, timeout=10)
            if response.status_code == 200:
                disallowed = []
                for line in response.text.splitlines():
                    stripped = line.strip()
                    if stripped.lower().startswith("disallow:"):
                        path = stripped.split(":", 1)[1].strip()
                        if path:
                            disallowed.append(path)
                return {"disallowed": disallowed, "error": None}
        except Exception as exc:
            return {"disallowed": [], "error": str(exc)}
        return {"disallowed": [], "error": None}

    def is_path_disallowed(self, url: str, disallowed_paths: list) -> bool:
        parsed = urlparse(url)
        path = parsed.path
        for blocked in disallowed_paths:
            if path.startswith(blocked):
                return True
        return False

    def fetch_html(self, url: str, use_playwright: bool = False) -> Tuple[Optional[str], Optional[str]]:
        if self._is_cached(url):
            cached = self._read_cache(url)
            return cached, None

        self._sleep_between_requests()
        if use_playwright:
            return self._fetch_with_playwright(url)
        return self._fetch_with_requests(url)

    def _fetch_with_requests(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, timeout=15, allow_redirects=True)
                if response.status_code == 200:
                    self._write_cache(url, response.text)
                    return response.text, None
                return None, f"HTTP {response.status_code}"
            except Exception as exc:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor ** attempt)
                    continue
                return None, str(exc)
        return None, "Max retries exceeded"

    def _fetch_with_playwright(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        for attempt in range(self.max_retries + 1):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)

                    page_text = page.content().lower()
                    blocked_tokens = [
                        "login",
                        "sign in",
                        "otp",
                        "captcha",
                        "recaptcha",
                        "verify your account",
                        "view contact no",
                        "enter your password",
                    ]

                    if any(token in page_text for token in blocked_tokens):
                        browser.close()
                        return None, "LOGIN_WALL_DETECTED"

                    html = page.content()
                    browser.close()
                    self._write_cache(url, html)
                    return html, None
            except Exception as exc:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor ** attempt)
                    continue
                return None, str(exc)
        return None, "Max retries exceeded"
