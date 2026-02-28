# 图片助记词扫描工具实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个离线工具，递归扫描目录图片，OCR 识别文字，检测并提取助记词，结果通过邮件发送。

**Architecture:** 模块化设计，scanner → hasher → db → ocr → detector → reporter → mailer 流水线。SQLite 持久化去重记录，双哈希机制（SHA256 + pHash）避免重复 OCR。

**Tech Stack:** Python 3.10+, PaddleOCR, SQLite3, imagehash, PyYAML, smtplib

---

## 前置准备

### Task 0: 初始化项目结构

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/.gitkeep`
- Create: `output/.gitkeep`

**Step 1: 创建 pyproject.toml**

```toml
[project]
name = "seed-scanner"
version = "0.1.0"
description = "Scan images for cryptocurrency seed phrases"
requires-python = ">=3.10"
dependencies = [
    "paddlepaddle",
    "paddleocr",
    "pillow",
    "imagehash",
    "pyyaml",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

**Step 2: 创建目录结构**

```bash
mkdir -p src tests data output
mkdir -p tests/unit
mkdir -p tests/fixtures
touch src/__init__.py tests/__init__.py data/.gitkeep output/.gitkeep
```

**Step 3: Commit**

```bash
git add .
git commit -m "chore: initialize project structure"
```

---

### Task 1: BIP39 词库数据文件

**Files:**
- Create: `data/bip39_wordlist.txt`
- Test: `tests/unit/test_wordlist.py`

**Step 1: Write the test**

```python
def test_wordlist_loads():
    from pathlib import Path

    wordlist_path = Path("data/bip39_wordlist.txt")
    assert wordlist_path.exists()

    words = wordlist_path.read_text().strip().split("\n")
    assert len(words) == 2048
    assert "abandon" in words
    assert "zoo" in words
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_wordlist.py -v
```
Expected: FAIL - file not found

**Step 3: Create wordlist file**

下载 BIP39 英文词库到 `data/bip39_wordlist.txt`（2048 个英文单词，每行一个）。

从 https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt 获取内容。

```bash
curl -o data/bip39_wordlist.txt https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_wordlist.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add data/bip39_wordlist.txt tests/unit/test_wordlist.py
git commit -m "feat: add BIP39 english wordlist"
```

---

### Task 2: 数据库模块 (db.py)

**Files:**
- Create: `src/db.py`
- Test: `tests/unit/test_db.py`

**Step 1: Write the test**

```python
import pytest
import sqlite3
from pathlib import Path
from src.db import Database


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    return Database(db_path)


def test_database_initialization(temp_db):
    assert temp_db.db_path.exists()


def test_table_creation(temp_db):
    conn = sqlite3.connect(temp_db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_files'")
    assert cursor.fetchone() is not None
    conn.close()


def test_insert_and_query_file(temp_db):
    temp_db.insert_file(
        file_hash="abc123",
        phash="def456",
        file_path="/test/image.png",
        file_size=1024,
        ocr_text="test text",
        has_seed=False,
        seed_phrase=None
    )

    result = temp_db.get_by_file_hash("abc123")
    assert result is not None
    assert result["file_hash"] == "abc123"
    assert result["phash"] == "def456"


def test_exists_by_file_hash(temp_db):
    temp_db.insert_file(
        file_hash="exists_hash",
        phash="phash1",
        file_path="/test/1.png",
        file_size=100,
        ocr_text="",
        has_seed=False,
        seed_phrase=None
    )

    assert temp_db.exists(file_hash="exists_hash") is True
    assert temp_db.exists(file_hash="not_exists") is False


def test_find_similar_phash(temp_db):
    # Insert a file with known phash
    temp_db.insert_file(
        file_hash="hash1",
        phash="aabbccdd",
        file_path="/test/1.png",
        file_size=100,
        ocr_text="",
        has_seed=False,
        seed_phrase=None
    )

    # Same phash should be found
    result = temp_db.find_by_phash_similarity("aabbccdd", threshold=5)
    assert len(result) == 1
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_db.py -v
```
Expected: FAIL - Database class not defined

**Step 3: Implement Database class**

```python
import sqlite3
from pathlib import Path
from typing import Optional
import imagehash


class Database:
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
                    file_hash TEXT NOT NULL,
                    phash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ocr_text TEXT,
                    has_seed BOOLEAN DEFAULT 0,
                    seed_phrase TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON processed_files(file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_phash ON processed_files(phash)")
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
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_db.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/db.py tests/unit/test_db.py
git commit -m "feat: add database module with SQLite backend"
```

---

### Task 3: 哈希模块 (hasher.py)

**Files:**
- Create: `src/hasher.py`
- Test: `tests/unit/test_hasher.py`

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from PIL import Image
from src.hasher import FileHasher


@pytest.fixture
def sample_image(tmp_path):
    """Create a simple test image"""
    img_path = tmp_path / "test.png"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(img_path)
    return img_path


def test_calculate_file_hash(sample_image):
    hasher = FileHasher()
    file_hash = hasher.calculate_file_hash(sample_image)

    assert isinstance(file_hash, str)
    assert len(file_hash) == 64  # SHA256 hex string length

    # Same file should produce same hash
    file_hash2 = hasher.calculate_file_hash(sample_image)
    assert file_hash == file_hash2


def test_calculate_phash(sample_image):
    hasher = FileHasher()
    phash = hasher.calculate_phash(sample_image)

    assert isinstance(phash, str)

    # Same image should produce same phash
    phash2 = hasher.calculate_phash(sample_image)
    assert phash == phash2


def test_phash_similarity(tmp_path):
    hasher = FileHasher()

    # Create two similar images (same color, slightly different size)
    img1_path = tmp_path / "img1.png"
    img2_path = tmp_path / "img2.png"

    img1 = Image.new('RGB', (100, 100), color='blue')
    img2 = Image.new('RGB', (105, 105), color='blue')

    img1.save(img1_path)
    img2.save(img2_path)

    phash1 = hasher.calculate_phash(img1_path)
    phash2 = hasher.calculate_phash(img2_path)

    # Similar images should have small hamming distance
    distance = hasher.hamming_distance(phash1, phash2)
    assert distance < 10  # Should be quite similar


def test_file_hash_different_content(tmp_path):
    hasher = FileHasher()

    # Two different images
    img1_path = tmp_path / "img1.png"
    img2_path = tmp_path / "img2.png"

    Image.new('RGB', (100, 100), color='red').save(img1_path)
    Image.new('RGB', (100, 100), color='blue').save(img2_path)

    hash1 = hasher.calculate_file_hash(img1_path)
    hash2 = hasher.calculate_file_hash(img2_path)

    assert hash1 != hash2
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_hasher.py -v
```
Expected: FAIL

**Step 3: Implement FileHasher**

```python
import hashlib
from pathlib import Path
import imagehash
from PIL import Image


class FileHasher:
    """Calculate file and perceptual hashes for images"""

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Calculate SHA256 hash of file contents"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_phash(file_path: Path) -> str:
        """Calculate perceptual hash (pHash) of image"""
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            phash = imagehash.phash(img)
            return str(phash)

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """Calculate Hamming distance between two phash strings"""
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_hasher.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/hasher.py tests/unit/test_hasher.py
git commit -m "feat: add file and perceptual hashing module"
```

---

### Task 4: 目录扫描模块 (scanner.py)

**Files:**
- Create: `src/scanner.py`
- Test: `tests/unit/test_scanner.py`
- Create: `tests/fixtures/sample1.png` (简单测试图片)

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from src.scanner import ImageScanner


def test_scan_directory(tmp_path):
    # Create test directory structure
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()

    # Create some image files
    (tmp_path / "img1.png").write_bytes(b"fake png")
    (tmp_path / "img2.jpg").write_bytes(b"fake jpg")
    (tmp_path / "sub1/img3.png").write_bytes(b"fake png")
    (tmp_path / "sub2/img4.bmp").write_bytes(b"fake bmp")

    # Create non-image file
    (tmp_path / "readme.txt").write_text("hello")

    scanner = ImageScanner()
    images = scanner.scan_directory(tmp_path)

    assert len(images) == 4
    assert all(img.suffix in ['.png', '.jpg', '.jpeg', '.bmp', '.webp'] for img in images)


def test_scan_non_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "root.png").write_bytes(b"fake")
    (tmp_path / "sub/nested.png").write_bytes(b"fake")

    scanner = ImageScanner(recursive=False)
    images = scanner.scan_directory(tmp_path)

    assert len(images) == 1
    assert images[0].name == "root.png"


def test_scan_empty_directory(tmp_path):
    scanner = ImageScanner()
    images = scanner.scan_directory(tmp_path)
    assert len(images) == 0


def test_scan_invalid_path():
    scanner = ImageScanner()
    with pytest.raises(FileNotFoundError):
        list(scanner.scan_directory(Path("/nonexistent")))


def test_supported_formats():
    scanner = ImageScanner()
    expected = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
    assert set(scanner.supported_formats) == expected
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_scanner.py -v
```
Expected: FAIL

**Step 3: Implement ImageScanner**

```python
from pathlib import Path
from typing import Iterator


class ImageScanner:
    """Scan directories for image files"""

    DEFAULT_FORMATS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']

    def __init__(self, recursive: bool = True, formats: list = None):
        self.recursive = recursive
        self.supported_formats = formats or self.DEFAULT_FORMATS

    def scan_directory(self, directory: Path) -> list[Path]:
        """
        Scan directory for image files.

        Args:
            directory: Path to scan

        Returns:
            List of image file paths
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {directory}")

        images = []

        if self.recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for path in directory.glob(pattern):
            if path.is_file() and path.suffix.lower() in self.supported_formats:
                images.append(path)

        return sorted(images)

    def scan_single_file(self, file_path: Path) -> Path:
        """Validate and return a single image file path"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        return file_path
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_scanner.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/scanner.py tests/unit/test_scanner.py
git commit -m "feat: add image directory scanner module"
```

---

### Task 5: 助记词检测模块 (seed_detector.py)

**Files:**
- Create: `src/seed_detector.py`
- Test: `tests/unit/test_seed_detector.py`

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from src.seed_detector import SeedDetector


@pytest.fixture
def detector():
    return SeedDetector(wordlist_path=Path("data/bip39_wordlist.txt"))


def test_load_wordlist(detector):
    assert len(detector.wordlist) == 2048
    assert "abandon" in detector.wordlist
    assert "zoo" in detector.wordlist


def test_detect_exact_12_words(detector):
    # Valid 12-word seed phrase
    text = "abandon ability able about above absent absorb abstract absurd abuse access accident"
    results = detector.detect(text)

    assert len(results) == 1
    assert len(results[0]) == 12
    assert results[0][0] == "abandon"


def test_detect_exact_24_words(detector):
    # Valid 24-word seed phrase
    text = ("abandon ability able about above absent absorb abstract absurd abuse access "
            "accident account accuse achieve acid acoustic acquire across act action actor")
    results = detector.detect(text)

    assert len(results) == 1
    assert len(results[0]) == 24


def test_detect_multiple_phrases(detector):
    text = ("abandon ability able about above absent absorb abstract absurd abuse access "
            "hello world some other text "
            "zoo zone zero year youth you young zone zoo zone zero")

    results = detector.detect(text)
    # Should detect the 12-word phrase at the start
    assert len(results) >= 1


def test_no_detection(detector):
    text = "hello world this is just some random text without any seed words"
    results = detector.detect(text)
    assert len(results) == 0


def test_fuzzy_match_with_typo(detector):
    # "aband0n" with zero instead of 'o'
    text = "aband0n ability able about above absent absorb abstract absurd abuse access accident"
    results = detector.detect(text, fuzzy=True)

    assert len(results) == 1
    assert results[0][0] == "abandon"  # Should correct the typo


def test_levenshtein_distance(detector):
    assert detector._levenshtein("abandon", "abandon") == 0
    assert detector._levenshtein("abandon", "aband0n") == 1
    assert detector._levenshtein("word", "w0rd") == 1
    assert detector._levenshtein("hello", "hallo") == 1


def test_fuzzy_threshold(detector):
    # Too different, should not match
    text = "abcd1234 xyz9999 ..."  # Gibberish
    results = detector.detect(text, fuzzy=True)
    assert len(results) == 0
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_seed_detector.py -v
```
Expected: FAIL

**Step 3: Implement SeedDetector**

```python
from pathlib import Path
from typing import List, Optional


class SeedDetector:
    """Detect cryptocurrency seed phrases in text"""

    SEED_LENGTHS = [12, 24]  # Standard BIP39 seed lengths
    FUZZY_THRESHOLD = 1      # Max edit distance for fuzzy matching

    def __init__(self, wordlist_path: Path = None):
        if wordlist_path is None:
            wordlist_path = Path(__file__).parent.parent / "data" / "bip39_wordlist.txt"

        self.wordlist_path = Path(wordlist_path)
        self.wordlist = self._load_wordlist()
        self.wordlist_set = set(self.wordlist)

    def _load_wordlist(self) -> List[str]:
        """Load BIP39 wordlist from file"""
        content = self.wordlist_path.read_text()
        return [word.strip().lower() for word in content.strip().split('\n') if word.strip()]

    def detect(self, text: str, fuzzy: bool = True) -> List[List[str]]:
        """
        Detect seed phrases in text.

        Args:
            text: OCR extracted text
            fuzzy: Enable fuzzy matching for OCR errors

        Returns:
            List of detected seed phrases (each is a list of words)
        """
        # Normalize text: lowercase, split by whitespace and common separators
        import re
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

        results = []

        # Slide through words looking for seed-length sequences
        for length in self.SEED_LENGTHS:
            for i in range(len(words) - length + 1):
                candidate = words[i:i + length]

                if self._is_valid_seed(candidate, fuzzy):
                    results.append(self._normalize_seed(candidate, fuzzy))

        return results

    def _is_valid_seed(self, words: List[str], fuzzy: bool) -> bool:
        """Check if word list is a valid seed phrase"""
        valid_count = 0

        for word in words:
            if word in self.wordlist_set:
                valid_count += 1
            elif fuzzy:
                # Try fuzzy matching
                if self._find_closest_word(word):
                    valid_count += 1

        # All words must be valid BIP39 words
        return valid_count == len(words)

    def _normalize_seed(self, words: List[str], fuzzy: bool) -> List[str]:
        """Normalize seed words (apply fuzzy corrections)"""
        if not fuzzy:
            return words

        return [self._find_closest_word(word) or word for word in words]

    def _find_closest_word(self, word: str) -> Optional[str]:
        """Find closest word in wordlist using Levenshtein distance"""
        if word in self.wordlist_set:
            return word

        # Only try fuzzy match for words with reasonable length
        if len(word) < 4:
            return None

        best_match = None
        best_distance = self.FUZZY_THRESHOLD + 1

        for candidate in self.wordlist:
            distance = self._levenshtein(word, candidate)
            if distance < best_distance:
                best_distance = distance
                best_match = candidate

        return best_match if best_distance <= self.FUZZY_THRESHOLD else None

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return SeedDetector._levenshtein(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost is 0 if characters match, 1 otherwise
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_seed_detector.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/seed_detector.py tests/unit/test_seed_detector.py
git commit -m "feat: add seed phrase detector with fuzzy matching"
```

---

### Task 6: OCR 引擎模块 (ocr_engine.py)

**Files:**
- Create: `src/ocr_engine.py`
- Test: `tests/unit/test_ocr_engine.py`

**Step 1: 下载测试图片到 tests/fixtures/**

```bash
# 创建一个简单测试图片用于 OCR
curl -L -o tests/fixtures/sample_text.png "https://via.placeholder.com/200x50/FFFFFF/000000?text=abandon+ability+able+about"
```

或者使用 Python 创建：

**Step 2: Write the test**

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from src.ocr_engine import OCREngine


def test_ocr_engine_initialization():
    engine = OCREngine(use_gpu=False)
    assert engine.use_gpu is False


def test_ocr_mock():
    """Test OCR with mocked paddleocr to avoid model download in tests"""
    engine = OCREngine(use_gpu=False)

    # Mock the ocr method
    engine.ocr = Mock(return_value=[
        [[(10, 10), (100, 10), (100, 30), (10, 30)], ('abandon ability', 0.95)],
        [[(10, 40), (100, 40), (100, 60), (10, 60)], ('able about', 0.92)]
    ])

    result = engine.extract_text(Path("fake.png"))
    assert "abandon ability" in result
    assert "able about" in result


def test_extract_text_empty_result():
    engine = OCREngine(use_gpu=False)
    engine.ocr = Mock(return_value=[None])

    result = engine.extract_text(Path("fake.png"))
    assert result == ""


def test_extract_text_no_detection():
    engine = OCREngine(use_gpu=False)
    engine.ocr = Mock(return_value=None)

    result = engine.extract_text(Path("fake.png"))
    assert result == ""
```

**Step 3: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_ocr_engine.py -v
```
Expected: FAIL

**Step 4: Implement OCREngine**

```python
from pathlib import Path
from typing import Optional


class OCREngine:
    """OCR engine using PaddleOCR"""

    def __init__(self, use_gpu: bool = False, lang: str = 'en'):
        self.use_gpu = use_gpu
        self.lang = lang
        self._ocr = None

    @property
    def ocr(self):
        """Lazy initialization of PaddleOCR"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False
            )
        return self._ocr

    def extract_text(self, image_path: Path) -> str:
        """
        Extract text from image using OCR.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text (joined lines)
        """
        result = self.ocr.ocr(str(image_path), cls=True)

        if not result or result[0] is None:
            return ""

        # Extract text from result structure
        lines = []
        for line in result[0]:
            if line:
                text = line[1][0]  # Text content
                confidence = line[1][1]  # Confidence score
                if confidence > 0.5:  # Filter low confidence
                    lines.append(text)

        return ' '.join(lines)

    def extract_text_with_boxes(self, image_path: Path) -> list:
        """
        Extract text with bounding box information.

        Returns:
            List of dicts: [{'text': '...', 'box': [...], 'confidence': 0.95}, ...]
        """
        result = self.ocr.ocr(str(image_path), cls=True)

        if not result or result[0] is None:
            return []

        boxes = []
        for line in result[0]:
            if line:
                boxes.append({
                    'box': line[0],
                    'text': line[1][0],
                    'confidence': line[1][1]
                })

        return boxes
```

**Step 5: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_ocr_engine.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add src/ocr_engine.py tests/unit/test_ocr_engine.py
git commit -m "feat: add PaddleOCR engine wrapper"
```

---

### Task 7: 报告生成模块 (reporter.py)

**Files:**
- Create: `src/reporter.py`
- Test: `tests/unit/test_reporter.py`

**Step 1: Write the test**

```python
import pytest
import json
from pathlib import Path
from datetime import datetime
from src.reporter import Reporter


@pytest.fixture
def sample_results():
    return [
        {
            "file_path": "/path/to/seed1.png",
            "file_hash": "abc123",
            "phash": "def456",
            "ocr_text": "abandon ability able about",
            "has_seed": True,
            "seed_phrase": "abandon ability able about above absent absorb abstract absurd abuse access accident"
        },
        {
            "file_path": "/path/to/none.png",
            "file_hash": "xyz789",
            "phash": "uvw012",
            "ocr_text": "some random text",
            "has_seed": False,
            "seed_phrase": None
        }
    ]


def test_generate_json_report(tmp_path, sample_results):
    output_dir = tmp_path / "output"
    reporter = Reporter(output_dir=output_dir)

    report_path = reporter.generate_json_report(sample_results)

    assert report_path.exists()
    assert report_path.suffix == ".json"

    data = json.loads(report_path.read_text())
    assert "scan_time" in data
    assert "total_files" in data
    assert "seeds_found" in data
    assert len(data["results"]) == 2


def test_generate_text_report(tmp_path, sample_results):
    output_dir = tmp_path / "output"
    reporter = Reporter(output_dir=output_dir)

    report_path = reporter.generate_text_report(sample_results)

    assert report_path.exists()
    assert report_path.suffix == ".txt"

    content = report_path.read_text()
    assert "助记词扫描报告" in content or "Seed Phrase Scan Report" in content
    assert "seed1.png" in content
    assert "abandon ability able" in content


def test_empty_results(tmp_path):
    reporter = Reporter(output_dir=tmp_path)

    report_path = reporter.generate_json_report([])
    data = json.loads(report_path.read_text())
    assert data["total_files"] == 0
    assert data["seeds_found"] == 0
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_reporter.py -v
```
Expected: FAIL

**Step 3: Implement Reporter**

```python
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class Reporter:
    """Generate scan reports in JSON and text formats"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json_report(self, results: List[Dict[str, Any]]) -> Path:
        """Generate JSON format report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"scan_result_{timestamp}.json"

        seeds_found = [r for r in results if r.get("has_seed")]

        report = {
            "scan_time": datetime.now().isoformat(),
            "total_files": len(results),
            "seeds_found": len(seeds_found),
            "results": results
        }

        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return report_path

    def generate_text_report(self, results: List[Dict[str, Any]]) -> Path:
        """Generate human-readable text report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"scan_result_{timestamp}.txt"

        seeds_found = [r for r in results if r.get("has_seed")]

        lines = [
            "=" * 60,
            "助记词扫描报告 / Seed Phrase Scan Report",
            "=" * 60,
            f"扫描时间 / Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"扫描文件总数 / Total Files: {len(results)}",
            f"发现助记词 / Seeds Found: {len(seeds_found)}",
            "=" * 60,
            "",
        ]

        if seeds_found:
            lines.append("⚠️  检测到的助记词 / Detected Seed Phrases:")
            lines.append("-" * 60)

            for i, result in enumerate(seeds_found, 1):
                lines.append(f"\n[{i}]")
                lines.append(f"  文件路径 / File: {result['file_path']}")
                lines.append(f"  助记词 / Seed: {result['seed_phrase']}")
                lines.append("")
        else:
            lines.append("✅ 未发现助记词 / No seed phrases detected.")

        lines.extend([
            "",
            "=" * 60,
            "详细结果 / Detailed Results:",
            "=" * 60,
            ""
        ])

        for result in results:
            status = "🚨 SEED" if result.get("has_seed") else "  -"
            lines.append(f"{status} {result['file_path']}")

        report_path.write_text('\n'.join(lines), encoding='utf-8')
        return report_path

    def generate_both(self, results: List[Dict[str, Any]]) -> tuple[Path, Path]:
        """Generate both JSON and text reports"""
        json_path = self.generate_json_report(results)
        text_path = self.generate_text_report(results)
        return json_path, text_path
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_reporter.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/reporter.py tests/unit/test_reporter.py
git commit -m "feat: add report generator for JSON and text output"
```

---

### Task 8: 邮件发送模块 (mailer.py)

**Files:**
- Create: `src/mailer.py`
- Test: `tests/unit/test_mailer.py`

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from src.mailer import Mailer


def test_mailer_initialization():
    mailer = Mailer(
        smtp_server="smtp.qq.com",
        smtp_port=587,
        username="test@qq.com",
        password="secret",
        to_address="recv@example.com"
    )
    assert mailer.smtp_server == "smtp.qq.com"


@patch('smtplib.SMTP')
def test_send_report(mock_smtp_class):
    mock_smtp = Mock()
    mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

    mailer = Mailer(
        smtp_server="smtp.qq.com",
        smtp_port=587,
        username="test@qq.com",
        password="secret",
        to_address="recv@example.com"
    )

    # Mock file content
    mock_report = Mock()
    mock_report.read_text.return_value = "Test report content"
    mock_report.exists.return_value = True

    result = mailer.send_report(
        subject="Test Report",
        body="See attached report",
        attachment=mock_report
    )

    assert result is True
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("test@qq.com", "secret")
    mock_smtp.send_message.assert_called_once()


def test_mailer_disabled():
    mailer = Mailer(enabled=False)
    result = mailer.send_report(subject="Test", body="Body")
    assert result is False
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_mailer.py -v
```
Expected: FAIL

**Step 3: Implement Mailer**

```python
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional


class Mailer:
    """Send scan reports via email"""

    def __init__(
        self,
        smtp_server: str = "smtp.qq.com",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        to_address: str = "",
        enabled: bool = True
    ):
        self.enabled = enabled
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_address = to_address

    def send_report(
        self,
        subject: str,
        body: str,
        attachment: Optional[Path] = None,
        attachment_name: Optional[str] = None
    ) -> bool:
        """
        Send report email with optional attachment.

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        if not all([self.username, self.password, self.to_address]):
            print("Mail configuration incomplete, skipping email notification")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = self.to_address
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if attachment and attachment.exists():
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read_bytes())
            encoders.encode_base64(part)

            filename = attachment_name or attachment.name
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_mailer.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/mailer.py tests/unit/test_mailer.py
git commit -m "feat: add email notification module"
```

---

### Task 9: 配置模块 (config.py)

**Files:**
- Create: `src/config.py`
- Create: `config.yaml.example`
- Test: `tests/unit/test_config.py`

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from src.config import Config


def test_default_config():
    config = Config()
    assert config.scanner['recursive'] is True
    assert '.png' in config.scanner['supported_formats']


def test_load_from_dict():
    data = {
        'scanner': {'recursive': False},
        'ocr': {'use_gpu': True}
    }
    config = Config(data)
    assert config.scanner['recursive'] is False
    assert config.ocr['use_gpu'] is True


def test_load_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scanner:
  recursive: false
  supported_formats: [".png", ".jpg"]

mail:
  enabled: true
  username: "test@qq.com"
""")

    config = Config.from_file(config_file)
    assert config.scanner['recursive'] is False
    assert config.mail['username'] == "test@qq.com"


def test_merge_command_line_args():
    config = Config()
    config.merge_args({'recursive': False, 'force': True})

    assert config.scanner['recursive'] is False
    assert config.force is True
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: FAIL

**Step 3: Implement Config**

```python
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """Configuration management"""

    DEFAULTS = {
        'scanner': {
            'supported_formats': ['.png', '.jpg', '.jpeg', '.bmp', '.webp'],
            'recursive': True
        },
        'ocr': {
            'use_gpu': False,
            'lang': 'en'
        },
        'detection': {
            'seed_lengths': [12, 24],
            'fuzzy_threshold': 1
        },
        'mail': {
            'enabled': False,
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'to_address': '',
            'subject': '助记词扫描结果 / Seed Scanner Report'
        },
        'output': {
            'directory': './output',
            'generate_json': True,
            'generate_txt': True
        },
        'database': {
            'path': './data/seed_scanner.db'
        },
        'force': False  # Command line only
    }

    def __init__(self, data: Optional[Dict] = None):
        self._config = self._deep_merge(self.DEFAULTS.copy(), data or {})

    @classmethod
    def from_file(cls, path: Path) -> 'Config':
        """Load config from YAML file"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        data = yaml.safe_load(path.read_text())
        return cls(data)

    def merge_args(self, args: Dict[str, Any]):
        """Merge command line arguments"""
        for key, value in args.items():
            if value is not None:
                self._config[key] = value

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @property
    def scanner(self) -> Dict:
        return self._config['scanner']

    @property
    def ocr(self) -> Dict:
        return self._config['ocr']

    @property
    def detection(self) -> Dict:
        return self._config['detection']

    @property
    def mail(self) -> Dict:
        return self._config['mail']

    @property
    def output(self) -> Dict:
        return self._config['output']

    @property
    def database(self) -> Dict:
        return self._config['database']

    @property
    def force(self) -> bool:
        return self._config.get('force', False)

    def __getitem__(self, key: str) -> Any:
        return self._config[key]
```

**Step 4: Create example config file**

```yaml
# config.yaml.example
scanner:
  supported_formats: [".png", ".jpg", ".jpeg", ".bmp", ".webp"]
  recursive: true

ocr:
  use_gpu: false
  lang: "en"

detection:
  seed_lengths: [12, 24]
  fuzzy_threshold: 1

mail:
  enabled: true
  smtp_server: "smtp.qq.com"
  smtp_port: 587
  username: "your_email@qq.com"
  password: "your_auth_code"
  to_address: "recipient@example.com"
  subject: "助记词扫描结果 / Seed Scanner Report"

output:
  directory: "./output"
  generate_json: true
  generate_txt: true

database:
  path: "./data/seed_scanner.db"
```

**Step 5: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add src/config.py config.yaml.example tests/unit/test_config.py
git commit -m "feat: add configuration management module"
```

---

### Task 10: 主程序入口 (main.py)

**Files:**
- Create: `src/main.py`
- Test: `tests/unit/test_main.py`

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


def test_parse_args():
    from src.main import parse_args

    args = parse_args(['/path/to/scan'])
    assert args.target == Path('/path/to/scan')
    assert args.config is None
    assert args.force is False

    args = parse_args(['/path/to/scan', '--config', 'cfg.yaml', '--force'])
    assert args.config == Path('cfg.yaml')
    assert args.force is True


@patch('src.main.ImageScanner')
@patch('src.main.Database')
@patch('src.main.FileHasher')
def test_scanner_pipeline(mock_hasher_class, mock_db_class, mock_scanner_class):
    from src.main import ScannerPipeline

    # Setup mocks
    mock_config = Mock()
    mock_config.scanner = {'recursive': True, 'supported_formats': ['.png']}
    mock_config.database = {'path': '/tmp/test.db'}
    mock_config.force = False

    pipeline = ScannerPipeline(mock_config)

    # Mock scanner returning one image
    mock_scanner = mock_scanner_class.return_value
    mock_scanner.scan_directory.return_value = [Path('/test/img.png')]

    # Mock hasher
    mock_hasher = mock_hasher_class.return_value
    mock_hasher.calculate_file_hash.return_value = 'filehash123'
    mock_hasher.calculate_phash.return_value = 'phash456'

    # Mock database
    mock_db = mock_db_class.return_value
    mock_db.exists.return_value = False
    mock_db.find_by_phash_similarity.return_value = []

    results = list(pipeline.process_directory(Path('/test')))

    assert len(results) == 1
    mock_scanner_class.assert_called_once_with(recursive=True, formats=['.png'])
```

**Step 2: Run test (expect FAIL)**

```bash
uv run pytest tests/unit/test_main.py -v
```
Expected: FAIL

**Step 3: Implement main.py**

```python
#!/usr/bin/env python3
"""
Seed Scanner - Detect cryptocurrency seed phrases in images
"""

import argparse
import sys
from pathlib import Path
from typing import Iterator
from datetime import datetime

from src.config import Config
from src.scanner import ImageScanner
from src.db import Database
from src.hasher import FileHasher
from src.ocr_engine import OCREngine
from src.seed_detector import SeedDetector
from src.reporter import Reporter
from src.mailer import Mailer


def parse_args(args=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Scan images for cryptocurrency seed phrases'
    )
    parser.add_argument(
        'target',
        type=Path,
        help='Directory or file to scan'
    )
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to config file'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force re-scan, ignore database records'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output directory for reports'
    )
    parser.add_argument(
        '--no-mail',
        action='store_true',
        help='Disable email notification'
    )
    return parser.parse_args(args)


class ScannerPipeline:
    """Main scanning pipeline coordinating all components"""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(Path(config.database['path']))
        self.hasher = FileHasher()
        self.ocr = OCREngine(
            use_gpu=config.ocr['use_gpu'],
            lang=config.ocr['lang']
        )
        self.detector = SeedDetector()
        self.results = []

    def process_directory(self, target: Path) -> Iterator[dict]:
        """Process all images in directory"""
        scanner = ImageScanner(
            recursive=self.config.scanner['recursive'],
            formats=self.config.scanner['supported_formats']
        )

        images = scanner.scan_directory(target)

        for img_path in images:
            result = self.process_image(img_path)
            if result:
                yield result

    def process_image(self, img_path: Path) -> dict:
        """Process single image"""
        file_hash = self.hasher.calculate_file_hash(img_path)
        phash = self.hasher.calculate_phash(img_path)

        result = {
            'file_path': str(img_path),
            'file_hash': file_hash,
            'phash': phash,
            'file_size': img_path.stat().st_size,
            'ocr_text': '',
            'has_seed': False,
            'seed_phrase': None
        }

        # Check exact duplicate
        if not self.config.force and self.db.exists(file_hash=file_hash):
            print(f"[SKIP] {img_path} (exact duplicate)")
            return None

        # Check similar image
        if not self.config.force:
            similar = self.db.find_by_phash_similarity(phash, threshold=5)
            if similar:
                print(f"[SKIP] {img_path} (similar to {similar[0]['file_path']})")
                return None

        print(f"[OCR] {img_path}")

        # OCR
        try:
            ocr_text = self.ocr.extract_text(img_path)
            result['ocr_text'] = ocr_text
        except Exception as e:
            print(f"[ERROR] OCR failed for {img_path}: {e}")
            result['ocr_text'] = f"ERROR: {e}"

        # Detect seed phrases
        if result['ocr_text']:
            seeds = self.detector.detect(result['ocr_text'], fuzzy=True)
            if seeds:
                result['has_seed'] = True
                result['seed_phrase'] = ' '.join(seeds[0])  # Take first match
                print(f"[ALERT] Seed phrase detected in {img_path}")

        # Save to database
        self.db.insert_file(
            file_hash=result['file_hash'],
            phash=result['phash'],
            file_path=result['file_path'],
            file_size=result['file_size'],
            ocr_text=result['ocr_text'],
            has_seed=result['has_seed'],
            seed_phrase=result['seed_phrase']
        )

        return result


def main():
    """Main entry point"""
    args = parse_args()

    # Load configuration
    if args.config and args.config.exists():
        config = Config.from_file(args.config)
    else:
        config = Config()

    # Merge command line arguments
    cli_args = {
        'force': args.force,
        'output': {'directory': str(args.output)} if args.output else None
    }
    config.merge_args({k: v for k, v in cli_args.items() if v is not None})

    # Initialize pipeline
    pipeline = ScannerPipeline(config)

    # Scan target
    print(f"Starting scan of: {args.target}")
    print("=" * 60)

    results = list(pipeline.process_directory(args.target))

    # Generate reports
    output_dir = Path(config.output['directory'])
    reporter = Reporter(output_dir)

    json_path, txt_path = None, None
    if config.output['generate_json']:
        json_path = reporter.generate_json_report(results)
        print(f"\nJSON report: {json_path}")

    if config.output['generate_txt']:
        txt_path = reporter.generate_text_report(results)
        print(f"Text report: {txt_path}")

    # Send email
    if config.mail['enabled'] and not args.no_mail:
        mailer = Mailer(**config.mail)

        seeds_found = [r for r in results if r['has_seed']]
        subject = config.mail['subject']
        body = f"""
Seed Scanner Report
==================
Scan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total files: {len(results)}
Seeds found: {len(seeds_found)}

See attached report for details.
        """.strip()

        attachment = txt_path or json_path
        if attachment:
            success = mailer.send_report(subject, body, attachment)
            if success:
                print(f"Email sent to {config.mail['to_address']}")

    # Print summary
    print("\n" + "=" * 60)
    print("Scan Complete")
    print(f"Total files processed: {len(results)}")
    print(f"Seed phrases found: {len(seeds_found)}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

**Step 4: Run test (expect PASS)**

```bash
uv run pytest tests/unit/test_main.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/main.py tests/unit/test_main.py
git commit -m "feat: add main entry point and scanner pipeline"
```

---

### Task 11: 集成测试和文档

**Files:**
- Create: `tests/integration/test_full_pipeline.py`
- Create: `README.md`

**Step 1: Write integration test**

```python
import pytest
from pathlib import Path
from PIL import Image
from src.main import ScannerPipeline
from src.config import Config


@pytest.fixture
def sample_image_with_seed(tmp_path):
    """Create a test image with seed phrase text"""
    # Note: This requires actual OCR to work, may need mocking
    img_path = tmp_path / "seed_wallet.png"

    # Create a simple test image
    img = Image.new('RGB', (400, 100), color='white')
    img.save(img_path)
    return img_path


def test_full_pipeline(tmp_path, sample_image_with_seed):
    """Test the full pipeline with mocked OCR"""
    from unittest.mock import Mock, patch

    config = Config()
    config._config['database']['path'] = str(tmp_path / "test.db")

    pipeline = ScannerPipeline(config)

    # Mock OCR to return a seed phrase
    pipeline.ocr.extract_text = Mock(return_value=
        "abandon ability able about above absent absorb abstract absurd abuse access accident")

    result = pipeline.process_image(sample_image_with_seed)

    assert result is not None
    assert result['has_seed'] is True
    assert 'abandon' in result['seed_phrase']
```

**Step 2: Create README.md**

```markdown
# Seed Scanner

加密货币助记词图片扫描工具 / Cryptocurrency Seed Phrase Scanner

## 功能

- 递归扫描目录中的图片文件
- 使用 PaddleOCR 离线识别图片文字
- 检测 12/24 词助记词（支持模糊匹配）
- 双哈希去重（文件哈希 + 感知哈希）
- 生成 JSON/TXT 报告
- 邮件发送扫描结果

## 安装

```bash
# 克隆仓库
git clone <repo>
cd seed-scanner

# 安装依赖
uv sync
```

## 配置

复制配置模板并编辑：

```bash
cp config.yaml.example config.yaml
nano config.yaml
```

## 使用

```bash
# 扫描目录
uv run python -m src.main /path/to/images

# 使用指定配置
uv run python -m src.main /path/to/images --config config.yaml

# 强制重新扫描
uv run python -m src.main /path/to/images --force

# 不发送邮件
uv run python -m src.main /path/to/images --no-mail
```

## 输出

扫描结果保存在 `output/` 目录：
- `scan_result_YYYYMMDD_HHMMSS.json` - 结构化数据
- `scan_result_YYYYMMDD_HHMMSS.txt` - 人类可读报告

## 安全提示

⚠️ 本工具处理敏感的助记词信息，请注意：
- 扫描结果文件包含助记词，请妥善保管
- 数据库文件 `data/seed_scanner.db` 缓存了 OCR 结果
- 建议扫描完成后清理输出文件
```

**Step 3: Run integration test**

```bash
uv run pytest tests/integration/ -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add tests/integration/test_full_pipeline.py README.md
git commit -m "test: add integration test and documentation"
```

---

## 执行选项

**计划完成并保存到 `docs/plans/2025-02-28-seed-scanner-implementation.md`**

**两种执行方式：**

**1. Subagent-Driven（当前会话）**
- 我为每个任务派遣新的子代理
- 每个任务完成后我进行代码审查
- 在当前工作区快速迭代

**2. Parallel Session（新会话）**
- 在新会话中打开工作区
- 使用 `executing-plans` skill 批量执行
- 带检查点的独立执行

**选择哪种方式？**

- 推荐 **方式1（Subagent-Driven）**：我可以边执行边审查，及时发现问题
- 如果需要你离线等待，可选 **方式2（Parallel Session）**
