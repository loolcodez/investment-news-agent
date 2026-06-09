from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


class ReportRepository:
    def __init__(self, base_dir: Path | str = "reports", archive: bool = True):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.archive = archive

    def write_report(self, markdown: str, payload: Dict) -> dict[str, Path]:
        latest_md = self.base_dir / "latest.md"
        latest_json = self.base_dir / "latest.json"

        latest_md.write_text(markdown, encoding="utf-8")
        latest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        archive_paths: dict[str, Path] = {"markdown": latest_md, "json": latest_json}
        if self.archive:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            archive_md = self.base_dir / f"{timestamp}.md"
            archive_json = self.base_dir / f"{timestamp}.json"
            archive_md.write_text(markdown, encoding="utf-8")
            archive_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            archive_paths.update({"archive_markdown": archive_md, "archive_json": archive_json})

        return archive_paths
