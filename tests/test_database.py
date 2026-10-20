import shutil
import uuid
from pathlib import Path

from shopmate.clients.database import _ensure_sqlite_directory

TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def test_sqlite_parent_directory_is_created():
    work_dir = TMP_ROOT / uuid.uuid4().hex
    db_file = work_dir / "nested" / "demo.db"

    _ensure_sqlite_directory(
        f"sqlite+aiosqlite:///{db_file.as_posix()}"
    )

    assert db_file.parent.is_dir()
    shutil.rmtree(work_dir, ignore_errors=True)


def test_mysql_url_is_untouched():
    # 非 SQLite 的 URL 不应触发任何目录创建
    _ensure_sqlite_directory(
        "mysql+aiomysql://root:123456@127.0.0.1:3306/demo?charset=utf8mb4"
    )
