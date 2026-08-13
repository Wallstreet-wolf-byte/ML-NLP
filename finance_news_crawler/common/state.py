from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set


class CrawlState:
    """SQLite 持久化的爬取状态管理器，支持断点续爬和去重。

    每个数据源独立追踪：
    - last_crawl_time: 上次成功爬取的截止时间
    - last_cursor: 翻页游标（可选，用于 API 类数据源）
    - total_crawled: 累计已爬取新闻条数
    - crawled_items: 已爬取的新闻 ID，防止重复入库

    用法:
        state = CrawlState(Path("crawler_data/crawl_state.db"))

        # 获取上次爬取时间（首次返回 None）
        last = state.get_last_crawl_time("jin10")

        # 爬取完成后更新状态
        state.update_crawl_state("jin10", datetime.now(), count=150)

        # 批量标记已爬取记录
        state.mark_items_crawled("jin10", ["id1", "id2", "id3"])

        # 检查某条是否已爬过
        if state.is_item_crawled("jin10", "id1"):
            skip...
    """

    def __init__(self, db_path: Path, *, item_retention_days: int = 30) -> None:
        self.db_path = db_path
        self.item_retention_days = item_retention_days
        self._ensure_dir()
        self._init_db()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_state (
                    source       TEXT PRIMARY KEY,
                    last_crawl_time TEXT,
                    last_cursor  TEXT DEFAULT '',
                    total_crawled INTEGER DEFAULT 0,
                    updated_at   TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crawled_items (
                    item_id  TEXT,
                    source   TEXT,
                    crawled_at TEXT,
                    PRIMARY KEY (item_id, source)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crawled_items_source
                ON crawled_items(source)
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # 爬取时间
    # ------------------------------------------------------------------

    def get_last_crawl_time(self, source: str) -> Optional[datetime]:
        """获取指定源上次成功爬取的截止时间。首次运行返回 None。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT last_crawl_time FROM crawl_state WHERE source = ?",
                (source,),
            ).fetchone()

        if not row or not row[0]:
            return None

        try:
            return datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def get_last_cursor(self, source: str) -> str:
        """获取指定源上次翻页游标。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT last_cursor FROM crawl_state WHERE source = ?",
                (source,),
            ).fetchone()
        return str(row[0]) if row and row[0] else ""

    def get_total_crawled(self, source: str) -> int:
        """获取指定源历史累计爬取条数。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT total_crawled FROM crawl_state WHERE source = ?",
                (source,),
            ).fetchone()
        return int(row[0]) if row and row[0] else 0

    def update_crawl_state(
        self,
        source: str,
        crawl_time: datetime,
        *,
        cursor: str = "",
        count: int = 0,
    ) -> None:
        """更新数据源爬取状态（UPSERT）。"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        crawl_time_str = crawl_time.strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO crawl_state (source, last_crawl_time, last_cursor, total_crawled, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    last_crawl_time = excluded.last_crawl_time,
                    last_cursor     = excluded.last_cursor,
                    total_crawled   = total_crawled + excluded.total_crawled,
                    updated_at      = excluded.updated_at
                """,
                (source, crawl_time_str, cursor, count, now_str),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # 已爬取条目管理
    # ------------------------------------------------------------------

    def is_item_crawled(self, source: str, item_id: str) -> bool:
        """检查某条记录是否已被爬取。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM crawled_items WHERE source = ? AND item_id = ?",
                (source, item_id),
            ).fetchone()
        return row is not None

    def mark_items_crawled(self, source: str, item_ids: List[str]) -> int:
        """批量标记已爬取记录，返回成功写入的条数。"""
        if not item_ids:
            return 0

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserted = 0

        with sqlite3.connect(str(self.db_path)) as conn:
            for item_id in item_ids:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO crawled_items (item_id, source, crawled_at) VALUES (?, ?, ?)",
                        (item_id, source, now_str),
                    )
                    inserted += 1
                except sqlite3.Error:
                    continue
            conn.commit()

        return inserted

    def get_crawled_item_ids(self, source: str) -> Set[str]:
        """获取指定源所有已爬取的 ID 集合（慎用，数据量大时可能很慢）。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT item_id FROM crawled_items WHERE source = ?",
                (source,),
            ).fetchall()
        return {row[0] for row in rows}

    # ------------------------------------------------------------------
    # 过期清理
    # ------------------------------------------------------------------

    def prune_old_items(self, days: Optional[int] = None) -> int:
        """清理超过 retention_days 天的已爬取记录，返回删除条数。"""
        retention = days if days is not None else self.item_retention_days
        cutoff = (datetime.now() - timedelta(days=retention)).strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "DELETE FROM crawled_items WHERE crawled_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount

    # ------------------------------------------------------------------
    # 重置
    # ------------------------------------------------------------------

    def reset_source(self, source: str) -> None:
        """重置指定数据源的全部状态（用于重新全量爬取）。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM crawl_state WHERE source = ?", (source,))
            conn.execute("DELETE FROM crawled_items WHERE source = ?", (source,))
            conn.commit()

    def reset_all(self) -> None:
        """重置所有数据源状态。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM crawl_state")
            conn.execute("DELETE FROM crawled_items")
            conn.commit()

    # ------------------------------------------------------------------
    # 状态摘要
    # ------------------------------------------------------------------

    def get_all_states(self) -> Dict[str, Dict[str, object]]:
        """返回所有数据源的状态摘要。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT source, last_crawl_time, last_cursor, total_crawled, updated_at FROM crawl_state"
            ).fetchall()

        result: Dict[str, Dict[str, object]] = {}
        for row in rows:
            result[row[0]] = {
                "last_crawl_time": row[1],
                "last_cursor": row[2],
                "total_crawled": row[3],
                "updated_at": row[4],
            }
        return result

    def print_summary(self) -> None:
        """打印状态摘要到控制台。"""
        states = self.get_all_states()
        if not states:
            print("[CrawlState] No previous crawl state found.")
            return

        print("[CrawlState] Previous crawl summary:")
        for source, info in states.items():
            print(
                f"  {source}: last={info['last_crawl_time']}, "
                f"total_crawled={info['total_crawled']}, "
                f"updated={info['updated_at']}"
            )


def compute_incremental_start(
    state: CrawlState,
    source: str,
    default_start: datetime,
) -> datetime:
    """计算增量模式下的起始时间。

    规则：
    - 如果之前有爬取记录，从上次结束时间开始（避免重复）
    - 否则使用配置的默认起始时间
    """
    last_time = state.get_last_crawl_time(source)
    if last_time is not None:
        print(f"  [{source}] Incremental mode: resuming from {last_time}")
        return last_time
    else:
        print(f"  [{source}] Incremental mode: first run, starting from {default_start}")
        return default_start
