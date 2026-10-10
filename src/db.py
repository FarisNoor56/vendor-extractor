import sqlite3
import os
from datetime import datetime
from typing import List, Tuple


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.init_schema()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_schema(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                url TEXT PRIMARY KEY,
                kind TEXT,
                status TEXT DEFAULT 'pending',
                last_fetched TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                source_url TEXT PRIMARY KEY,
                name TEXT,
                city TEXT,
                address TEXT,
                gst TEXT,
                contact_person TEXT,
                phone TEXT,
                phone_type TEXT,
                categories TEXT,
                source_site TEXT,
                scraped_at TEXT
            )
            """
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_vendors_gst ON vendors(gst)"
        )

        conn.commit()
        conn.close()

    def queue_url(self, url: str, kind: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO queue (url, kind, status) VALUES (?, ?, 'pending')",
                (url, kind),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_pending_urls(self, limit: int = 100) -> List[Tuple[str, str]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT url, kind FROM queue WHERE status = 'pending' LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def mark_done(self, url: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE queue SET status = 'done', last_fetched = ? WHERE url = ?",
            (datetime.utcnow().isoformat(), url),
        )
        conn.commit()
        conn.close()

    def mark_failed(self, url: str, reason: str = ""):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE queue SET status = 'failed', last_fetched = ? WHERE url = ?",
            (datetime.utcnow().isoformat(), url),
        )
        conn.commit()
        conn.close()

    def upsert_vendor(self, vendor_data: dict) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        source_url = vendor_data.get("source_url")
        gst = vendor_data.get("gst") or ""

        if gst:
            cursor.execute("SELECT source_url FROM vendors WHERE gst = ?", (gst,))
            existing = cursor.fetchone()
            if existing and existing[0] != source_url:
                conn.close()
                return False

        cursor.execute(
            """
            INSERT INTO vendors (
                source_url, name, city, address, gst, contact_person,
                phone, phone_type, categories, source_site, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET
                name = excluded.name,
                city = excluded.city,
                address = excluded.address,
                gst = excluded.gst,
                contact_person = excluded.contact_person,
                phone = excluded.phone,
                phone_type = excluded.phone_type,
                categories = excluded.categories,
                source_site = excluded.source_site,
                scraped_at = excluded.scraped_at
            """,
            (
                source_url,
                vendor_data.get("name", ""),
                vendor_data.get("city", ""),
                vendor_data.get("address", ""),
                gst,
                vendor_data.get("contact_person", ""),
                vendor_data.get("phone", ""),
                vendor_data.get("phone_type", "direct"),
                vendor_data.get("categories", ""),
                vendor_data.get("source_site", "indiamart"),
                vendor_data.get("scraped_at", datetime.utcnow().isoformat()),
            ),
        )
        conn.commit()
        conn.close()
        return True

    def get_all_vendors(self) -> List[dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source_url, name, city, address, gst, contact_person,
                   phone, phone_type, categories, source_site, scraped_at
            FROM vendors
            ORDER BY scraped_at DESC
            """
        )
        columns = [description[0] for description in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_queue_stats(self) -> dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM queue GROUP BY status")
        stats = {key: value for key, value in cursor.fetchall()}
        conn.close()
        return stats

    def get_vendor_count(self) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM vendors")
        count = cursor.fetchone()[0]
        conn.close()
        return count
