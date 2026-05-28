import aiosqlite
import os

_DEFAULT_DB_PATH = "06_DATA/chromatic.sqlite"


def _db_path() -> str:
    return os.getenv("CHROMATIC_DB_PATH", _DEFAULT_DB_PATH)


# Module-level alias kept for backwards compatibility; callers should prefer _db_path()
DB_PATH = _DEFAULT_DB_PATH


async def init_db():
    path = _db_path()
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS missions (
            mission_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS magnet_events (
            event_id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS beads (
            bead_id TEXT PRIMARY KEY,
            mission_id TEXT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        await db.commit()


async def get_db():
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        yield db
