#!/usr/bin/env python3
"""每日板块快照守护 —— 供 LaunchAgent 定时调用，也可手动跑。

为什么需要它（2026-08-13）：板块逐日史的长期可续接来源是收盘后的全板块 `clist` 快照。
东财 `push2his` 历史端点已被 (出口 IP × 路径) 级封锁；既有缺口虽曾用短期 Tushare
权限补回，但凭据不持久化、也不接入日常自动任务。因此漏跑仍可能成为不可补的永久空洞，
而「连续 N 日」条件、板块 MA20 与死亡条件误报回测全都依赖连续序列。

三件事，缺一不可：
  1. **交易日守卫**：`fetch_clist_snapshot` 只按调用方给的 `trade_date` 打戳、不校验交易日。
     周末或节假日直接跑，会把上一交易日的值盖上非交易日的日期，制造**幽灵交易日**。
     判据用腾讯行情上证指数的最后成交时间戳（零鉴权、不封 IP、自校验），不依赖任何
     需要鉴权的交易日历。
  2. **落盘校验**：跑完必须回查数据库确认当日三类板块都真的落了行，不看命令退出码。
  3. **缺口审计**：列出库里最近的交易日序列，当日缺失时大声报错（退出码 1，供 launchd 记录）。

幂等：`store_observations` 是 upsert，重复跑安全。

装成定时任务（macOS launchd；plist 含绝对路径，故不入库，按需自行生成）：
    LABEL=com.taosheng.a-stock-data.board-snapshot
    # 写 ~/Library/LaunchAgents/$LABEL.plist：
    #   ProgramArguments = [<能 import requests 的 python3 绝对路径>, <本文件绝对路径>]
    #   StartCalendarInterval = 周一至周五各两档 15:40 与 20:00
    #     （15:40 收盘后首跑；20:00 兜底。机器睡眠时 launchd 会在唤醒后补跑。）
    #   RunAtLoad = true       长时间关机后开机即补当日快照
    #   StandardOutPath / StandardErrorPath → ~/Library/Logs/a-stock-data/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$LABEL.plist
卸载：
    launchctl bootout gui/$(id -u)/$LABEL && rm ~/Library/LaunchAgents/$LABEL.plist
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_fund_flow_cache import default_db_path, init_db, sync_clist_snapshot  # noqa: E402

SHANGHAI = ZoneInfo("Asia/Shanghai")
LOG_PATH = Path.home() / "Library/Logs/a-stock-data/board_snapshot.log"
BOARD_TYPES = ("industry", "concept", "region")
# 收盘 15:00，行情落定留 30 分钟余量；与 board_fund_flow_cache 的 15:30 闸门一致。
EARLIEST = time(15, 35)

# ── 备份 ──────────────────────────────────────────────────────────────
# 为什么绑在「写入成功」而不是绑时钟：库只在快照落盘那一刻变化，而这台机器
# 会关机、会睡眠。按时钟跑既会漏（关机）又会空转（当天无新数据）；绑写入则
# 备份频率自动等于数据变化频率，关机多久都不影响——开机后快照补跑，备份跟着补。
BACKUP_DIR = Path.home() / ".local/share/taosheng/a-stock-backups"
BACKUP_KEEP = 10          # 保留最近 10 个交易日，约 13 MB
MANIFEST = "_manifest.json"


def log(msg: str) -> None:
    stamp = datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def last_trade_date() -> str | None:
    """上证指数最后成交日（YYYY-MM-DD）。腾讯行情字段 30 = YYYYMMDDHHMMSS。

    零鉴权、不封 IP。取不到返回 None —— 此时**不猜**，直接放弃本轮，
    宁可漏一次自动跑（复盘第 6 步还会兜底），也不要写错日期的行。
    """
    try:
        req = urllib.request.Request("https://qt.gtimg.cn/q=sh000001")
        req.add_header("User-Agent", "Mozilla/5.0")
        raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk")
        fields = raw.split('"')[1].split("~")
        stamp = fields[30]
        if len(stamp) < 8 or not stamp[:8].isdigit():
            return None
        return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    except Exception as exc:  # noqa: BLE001
        log(f"WARN 取上证指数时间戳失败: {type(exc).__name__}: {exc}")
        return None


def rows_on(db: Path, date: str) -> dict[str, int]:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        return {
            bt: conn.execute(
                "SELECT count(*) FROM observations WHERE trade_date=? AND board_type=?",
                (date, bt),
            ).fetchone()[0]
            for bt in BOARD_TYPES
        }


def recent_dates(db: Path, limit: int = 8) -> list[tuple[str, int]]:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        return list(
            conn.execute(
                "SELECT trade_date, count(*) FROM observations "
                "GROUP BY trade_date ORDER BY trade_date DESC LIMIT ?",
                (limit,),
            )
        )


def export_backup(db: Path, date: str) -> bool:
    """把库导成 gzip SQL dump 落进 iCloud 工作台。返回是否成功。

    三道闸门，任一不过就不覆盖轮换位：
      1. `PRAGMA integrity_check` 必须 ok；
      2. 行数**只增不减**（本库是 upsert-only、无删除）——比上次备份少即视为
         数据损坏或被误删，写成 `.SUSPECT` 并报错，**绝不让坏副本顶掉好副本**；
      3. 导出后立刻回读校验（gunzip 能解开且含建表语句）。
    """
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            if (conn.execute("PRAGMA integrity_check").fetchone() or [""])[0] != "ok":
                log("FAIL 备份中止：库完整性检查未通过")
                return False
            rows = conn.execute("SELECT count(*) FROM observations").fetchone()[0]
            max_date = conn.execute(
                "SELECT max(trade_date) FROM observations").fetchone()[0]
            dump = "\n".join(conn.iterdump()).encode("utf-8")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        man_path = BACKUP_DIR / MANIFEST
        manifest = {}
        if man_path.exists():
            try:
                manifest = json.loads(man_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                log("WARN 备份清单损坏，按空清单继续")

        prev_max = max((e.get("rows", 0) for e in manifest.get("files", {}).values()),
                       default=0)
        suspect = rows < prev_max
        name = f"board_fund_flow-{date}{'.SUSPECT' if suspect else ''}.sql.gz"
        target = BACKUP_DIR / name
        target.write_bytes(gzip.compress(dump, 9))

        # 回读校验
        head = gzip.decompress(target.read_bytes())[:2000].decode("utf-8", "ignore")
        if "CREATE TABLE" not in head:
            log(f"FAIL 备份回读校验不通过，已删除 {name}")
            target.unlink(missing_ok=True)
            return False

        if suspect:
            log(f"FAIL 行数倒退（{rows} < 历史最高 {prev_max}），已存为 {name} "
                f"且**未进入轮换**——请先查清库是否被误删或损坏，勿直接采用")
            return False

        manifest.setdefault("files", {})[name] = {
            "rows": rows, "max_trade_date": max_date,
            "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "exported_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        }
        manifest["restore"] = (
            "gunzip -c board_fund_flow-<日期>.sql.gz | "
            "sqlite3 ~/Library/Application\\ Support/a-stock-data/board_fund_flow.sqlite3")
        manifest["note"] = (
            "本库是板块逐日资金史的生产副本；虽做过一次性 Tushare 补洞，"
            "但 push2his 已被封且没有长期补洞凭据，不能假定可完整重建。"
            "备份绑在每日快照写入成功那一刻，不按时钟跑。行数只增不减；"
            ".SUSPECT 文件表示该次导出行数倒退，需人工核查后才可使用。")

        # 轮换：只留最近 BACKUP_KEEP 个正常备份，.SUSPECT 一律保留不清
        normal = sorted(n for n in manifest["files"] if ".SUSPECT" not in n)
        for stale in normal[:-BACKUP_KEEP]:
            (BACKUP_DIR / stale).unlink(missing_ok=True)
            manifest["files"].pop(stale, None)

        man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        log(f"备份 OK {name}（{rows} 条 · 至 {max_date} · "
            f"{target.stat().st_size // 1024} KB · 现存 {len(normal[-BACKUP_KEEP:])} 份）")
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"FAIL 备份异常: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    now = datetime.now(SHANGHAI)
    today = now.date().isoformat()
    db = Path(init_db(default_db_path()))

    if "--backup-only" in sys.argv:            # 手动补备份，不碰快照
        return 0 if export_backup(db, today) else 1

    traded = last_trade_date()
    if traded is None:
        log("SKIP 无法确认交易日（行情源不可达），本轮不落盘")
        return 0
    if traded != today:
        log(f"SKIP {today} 非交易日或行情未更新（上证指数最后成交日 {traded}）")
        return 0
    if now.time() < EARLIEST:
        log(f"SKIP {today} 是交易日但尚未到 {EARLIEST.strftime('%H:%M')}，等下一档")
        return 0

    before = rows_on(db, today)
    if all(before[bt] > 0 for bt in BOARD_TYPES):
        log(f"OK {today} 已落盘，跳过（幂等）：{before}")
        # 落盘幂等，但备份可能上次没成（iCloud 不可写 / 当时报错），缺了就补
        if not (BACKUP_DIR / f"board_fund_flow-{today}.sql.gz").exists():
            log("  当日备份缺失，补做")
            return 0 if export_backup(db, today) else 1
        return 0

    try:
        counts = sync_clist_snapshot(db, today, board_types=BOARD_TYPES)
        log(f"落盘返回 {counts}")
    except Exception as exc:  # noqa: BLE001
        log(f"FAIL {today} 快照失败: {type(exc).__name__}: {exc}")
        log("  → 该交易日可能永久缺失：push2his 已被封、未配置长期 Tushare 凭据、"
            "clist 只给当日值。请尽快手动重试 "
            "`board_fund_flow_cache.py snapshot --trade-date " + today + "`")
        return 1

    after = rows_on(db, today)
    missing = [bt for bt in BOARD_TYPES if after[bt] == 0]
    if missing:
        log(f"FAIL {today} 落盘后校验不通过，缺板块类型 {missing}；实际 {after}")
        return 1

    log(f"OK {today} 落盘校验通过：{after}")
    log("  库内最近交易日：" + " · ".join(f"{d}({n})" for d, n in recent_dates(db)))

    # 写入成功 → 立刻备份。备份失败不回滚快照（数据已经安全落库），但退出码非 0
    # 让 launchd 记下来，因为「有数据但没副本」正是 A3 要防的状态。
    return 0 if export_backup(db, today) else 1


if __name__ == "__main__":
    sys.exit(main())
