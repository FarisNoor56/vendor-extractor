import json
import re
from datetime import datetime
from typing import Dict, Optional

from bs4 import BeautifulSoup


class VendorParser:
    def __init__(self, source_site: str = "indiamart"):
        self.source_site = source_site

    def parse_profile(self, html: str, url: str, city: str) -> Optional[Dict]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            vendor = {
                "source_url": url,
                "city": city,
                "source_site": self.source_site,
                "scraped_at": datetime.utcnow().isoformat(),
            }

            json_data = self._extract_json_ld(soup)
            if json_data:
                vendor.update(json_data)
            else:
                vendor.update(self._extract_with_selectors(soup))

            for key in ["name", "address", "gst", "contact_person", "phone", "phone_type", "categories"]:
                vendor.setdefault(key, "")

            vendor["phone_type"] = self._determine_phone_type(vendor.get("phone", ""))
            return vendor
        except Exception:
            return None

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
            except Exception:
                continue

            if isinstance(data, dict) and data.get("@type") == "Organization":
                return {
                    "name": data.get("name", ""),
                    "address": self._format_address(data.get("address", {})),
                    "phone": data.get("telephone", ""),
                    "gst": self._extract_gst(str(data.get("taxID", ""))),
                    "contact_person": self._contact_from_ld(data.get("contactPoint")),
                    "categories": self._extract_categories(data.get("category", [])),
                }

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Organization":
                        return {
                            "name": item.get("name", ""),
                            "address": self._format_address(item.get("address", {})),
                            "phone": item.get("telephone", ""),
                            "gst": self._extract_gst(str(item.get("taxID", ""))),
                            "contact_person": self._contact_from_ld(item.get("contactPoint")),
                            "categories": self._extract_categories(item.get("category", [])),
                        }
        return None

    def _extract_with_selectors(self, soup: BeautifulSoup) -> Dict:
        vendor = {}
        vendor["name"] = self._extract_text(soup, ["h1.company-name", ".company-title", "h1[itemprop='name']", ".vendor-name"])
        vendor["address"] = self._extract_text(soup, [".company-address", "[itemprop='address']", ".vendor-address", ".location"])
        vendor["gst"] = self._extract_gst(self._extract_text(soup, [".gst-number", "[data-gst]", ".tax-id"]))
        vendor["contact_person"] = self._extract_text(soup, [".contact-person", "[itemprop='contactPoint'] .name", ".primary-contact"])
        raw_phone = self._extract_text(soup, [".phone-number", "[itemprop='telephone']", ".contact-phone", ".mobile"])
        vendor["phone"] = self._extract_phone(raw_phone)
        vendor["categories"] = self._extract_text(soup, [".categories", ".product-categories", "[itemprop='category']"])
        return vendor

    def _extract_text(self, soup: BeautifulSoup, selectors: list) -> str:
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(" ", strip=True)
                if text:
                    return text
        return ""

    def _contact_from_ld(self, value) -> str:
        if isinstance(value, dict):
            return value.get("name", "")
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return first.get("name", "")
        return ""

    def _extract_categories(self, categories) -> str:
        if isinstance(categories, list):
            parts = []
            for entry in categories:
                if isinstance(entry, dict):
                    candidate = entry.get("name") or entry.get("@id") or ""
                    if candidate:
                        parts.append(str(candidate))
                elif isinstance(entry, str):
                    parts.append(entry)
            return ", ".join(parts)
        return str(categories) if categories else ""

    def _format_address(self, value) -> str:
        if isinstance(value, dict):
            parts = [
                value.get("streetAddress", ""),
                value.get("addressLocality", ""),
                value.get("postalCode", ""),
            ]
            return ", ".join([p for p in parts if p])
        if isinstance(value, str):
            return value
        return ""

    def _extract_gst(self, text: str) -> str:
        if not text:
            return ""
        if "hidden" in text.lower() or "***" in text or "view contact" in text.lower():
            return "hidden"
        match = re.search(r"\d{2}[A-Z]{5}\d{4}[A-Z0-9]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1}", text.upper())
        if match:
            return match.group(0)
        return text.strip()

    def _extract_phone(self, text: str) -> str:
        if not text:
            return ""
        if "hidden" in text.lower() or "***" in text or "view contact" in text.lower():
            return "hidden"
        return text.strip()

    def _determine_phone_type(self, phone: str) -> str:
        if not phone or phone == "hidden":
            return "direct"
        if "+91 80" in phone or "+9180" in phone:
            if re.search(r"(ext|extension|x)\s*\d+", phone, re.IGNORECASE):
                return "IndiaMART virtual line"
        return "direct"
