import argparse
import logging
import sys

import yaml

from src.crawler import CategoryCrawler
from src.db import Database
from src.export import ExcelExporter
from src.fetch import FetchManager
from src.parser import VendorParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VendorExtractor:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.db = Database(self.config["output"]["db_path"])
        self.fetch_manager = FetchManager(
            html_cache_dir=self.config["output"]["html_cache_dir"],
            delay_min=self.config["crawling"]["delay_min"],
            delay_max=self.config["crawling"]["delay_max"],
            max_retries=self.config["crawling"]["max_retries"],
            backoff_factor=self.config["crawling"]["backoff_factor"],
        )
        self.parser = VendorParser(source_site="indiamart")
        self.city = self.config["city"]

    def _load_config(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def crawl(self):
        total_collected = 0
        for name, data in self.config.get("categories", {}).items():
            url = data.get("url")
            if not url:
                continue

            robots = self.fetch_manager.check_robots_txt(url)
            if robots["error"]:
                logger.warning("robots.txt warning for %s: %s", url, robots["error"])
            if robots["disallowed"] and self.fetch_manager.is_path_disallowed(url, robots["disallowed"]):
                logger.warning("Skipping disallowed URL per robots.txt: %s", url)
                continue

            crawler = CategoryCrawler(self.fetch_manager, self.db, self.city, self.config["crawling"]["max_pages"])
            total_collected += crawler.crawl_category(url)

        logger.info("Collected %s profile URLs", total_collected)
        logger.info("Queue stats: %s", self.db.get_queue_stats())

    def parse(self):
        parsed_count = 0
        while True:
            pending = self.db.get_pending_urls(limit=100)
            if not pending:
                break

            for url, kind in pending:
                if kind != "profile":
                    self.db.mark_done(url)
                    continue

                html, error = self.fetch_manager.fetch_html(url, use_playwright=True)
                if error:
                    if "LOGIN_WALL_DETECTED" in error:
                        logger.error("Blocking login/captcha wall detected while parsing %s", url)
                        self.db.mark_failed(url, error)
                        sys.exit(1)
                    logger.warning("Failed to fetch %s: %s", url, error)
                    self.db.mark_failed(url, error)
                    continue

                vendor = self.parser.parse_profile(html, url, self.city)
                if vendor:
                    self.db.upsert_vendor(vendor)
                    parsed_count += 1
                self.db.mark_done(url)

        logger.info("Parsed %s vendor records", parsed_count)

    def export(self):
        exporter = ExcelExporter(self.db, self.config["output"]["excel_output"])
        exporter.export()

    def all(self):
        self.crawl()
        self.parse()
        self.export()


def main():
    parser = argparse.ArgumentParser(description="vendor-extractor")
    parser.add_argument("command", choices=["crawl", "parse", "export", "all"])
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    extractor = VendorExtractor(args.config)

    if args.command == "crawl":
        extractor.crawl()
    elif args.command == "parse":
        extractor.parse()
    elif args.command == "export":
        extractor.export()
    else:
        extractor.all()


if __name__ == "__main__":
    main()
