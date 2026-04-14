from pathlib import Path
from datetime import datetime
import shutil
import sqlite3

from logger_setup import get_logger

logger = get_logger("db_guard")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "latest_stable.db"
BACKUP_DIR = BASE_DIR / "backups"
MAX_BACKUPS = 30


def ensure_db_exists() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        logger.warning("Banco não existe. Criando: %s", DB_PATH)
        DB_PATH.touch()


def check_db_health() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1;")
        conn.close()
        logger.info("Banco saudável.")
        return True
    except Exception as e:
        logger.error("Falha no banco: %s", e)
        return False


def create_backup() -> Path | None:
    try:
        ensure_db_exists()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"escala_{ts}.db"
        shutil.copy2(DB_PATH, backup_path)
        logger.info("Backup criado: %s", backup_path)
        prune_old_backups()
        return backup_path
    except Exception as e:
        logger.error("Erro ao criar backup: %s", e)
        return None


def prune_old_backups() -> None:
    backups = sorted(
        BACKUP_DIR.glob("escala_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for f in backups[MAX_BACKUPS:]:
        try:
            f.unlink()
            logger.info("Backup antigo removido: %s", f)
        except Exception as e:
            logger.error("Erro ao remover backup antigo %s: %s", f, e)


def restore_latest_backup() -> bool:
    try:
        backups = sorted(
            BACKUP_DIR.glob("escala_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not backups:
            logger.warning("Nenhum backup para restore.")
            return False

        shutil.copy2(backups[0], DB_PATH)
        logger.warning("Banco restaurado de: %s", backups[0])
        return True
    except Exception as e:
        logger.error("Erro no restore: %s", e)
        return False
