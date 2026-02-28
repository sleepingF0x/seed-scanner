"""Database module for seed scanner."""

import sqlite3
from pathlib import Path
from typing import Optional
import imagehash


class Database:
    """SQLite database for storing processed file information."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT UNIQUE NOT NULL,
                    phash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    ocr_text TEXT,
                    has_seed BOOLEAN DEFAULT 0,
                    seed_phrase TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash ON processed_files(file_hash)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_phash ON processed_files(phash)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_has_seed ON processed_files(has_seed)
            """)
            conn.commit()

    def insert_file(
        self,
        file_hash: str,
        phash: str,
        file_path: str,
        file_size: int,
        ocr_text: str,
        has_seed: bool,
        seed_phrase: Optional[str]
    ) -> int:
        """Insert a processed file record"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO processed_files
                   (file_hash, phash, file_path, file_size, ocr_text, has_seed, seed_phrase)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (file_hash, phash, file_path, file_size, ocr_text, has_seed, seed_phrase)
            )
            conn.commit()
            return cursor.lastrowid

    def get_by_file_hash(self, file_hash: str) -> Optional[dict]:
        """Get record by exact file hash"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM processed_files WHERE file_hash = ?",
                (file_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def exists(self, file_hash: str) -> bool:
        """Check if file hash exists in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_files WHERE file_hash = ? LIMIT 1",
                (file_hash,)
            )
            return cursor.fetchone() is not None

    def find_by_phash_similarity(self, phash: str, threshold: int = 5) -> list:
        """Find records with similar perceptual hash"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM processed_files")
            rows = cursor.fetchall()

            results = []
            target_hash = imagehash.hex_to_hash(phash)

            for row in rows:
                stored_hash = imagehash.hex_to_hash(row["phash"])
                distance = target_hash - stored_hash
                if distance <= threshold:
                    results.append(dict(row))

            return results

    def get_files_with_seeds(self) -> list:
        """Get all records that contain seed phrases"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM processed_files WHERE has_seed = 1 ORDER BY processed_at DESC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Get processing statistics"""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
            with_seed = conn.execute(
                "SELECT COUNT(*) FROM processed_files WHERE has_seed = 1"
            ).fetchone()[0]
            return {"total_processed": total, "seeds_found": with_seed}
