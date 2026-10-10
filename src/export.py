import logging

import pandas as pd
from openpyxl.styles import Font

logger = logging.getLogger(__name__)


class ExcelExporter:
    def __init__(self, db, output_path: str):
        self.db = db
        self.output_path = output_path

    def export(self):
        vendors = self.db.get_all_vendors()
        if not vendors:
            logger.warning("No vendor rows available for export.")
            return

        df = pd.DataFrame(vendors)
        columns = [
            "source_url",
            "name",
            "city",
            "address",
            "gst",
            "contact_person",
            "phone",
            "phone_type",
            "categories",
            "source_site",
            "scraped_at",
        ]
        df = df[columns]

        with pd.ExcelWriter(self.output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Vendors", index=False)
            ws = writer.sheets["Vendors"]
            ws.auto_filter.ref = f"A1:K{len(df) + 1}"

            for cell in ws[1]:
                cell.font = Font(bold=True)

            for idx, column in enumerate(columns, start=1):
                max_len = max(len(str(column)), *(len(str(v)) for v in df[column].fillna("").astype(str)))
                ws.column_dimensions[chr(64 + idx)].width = min(max_len + 2, 50)

        logger.info("Exported %s vendors to %s", len(df), self.output_path)
        print(f"✓ Exported {len(df)} vendors to {self.output_path}")
