import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db.models import Load

logger = logging.getLogger(__name__)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run() -> int:
    settings = get_settings()
    path = Path(settings.loads_json_path)
    if not path.exists():
        raise FileNotFoundError(f"seed file not found: {path}")

    with path.open() as f:
        rows = json.load(f)

    for row in rows:
        row["pickup_datetime"] = _parse_iso(row["pickup_datetime"])
        row["delivery_datetime"] = _parse_iso(row["delivery_datetime"])

    engine = create_engine(settings.database_url, future=True)
    with engine.begin() as conn:
        for row in rows:
            stmt = pg_insert(Load.__table__).values(**row)
            update_cols = {
                c.name: c for c in stmt.excluded if c.name not in ("load_id", "created_at")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["load_id"],
                set_=update_cols,
            )
            conn.execute(stmt)

    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"seeded {count} loads")
