import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH = Path("data/instock.db")

# Decision thresholds — edit these to tune pass/fail criteria
THRESHOLDS = {
    "success_rate":  {"green": 0.85, "yellow": 0.60},   # higher is better
    "bans_per_day":  {"green": 1.0,  "yellow": 3.0},    # lower is better
    "uptime_pct":    {"green": 0.95, "yellow": 0.85},   # higher is better
}


def _verdict_hi(value: float, metric: str) -> str:
    """Verdict for metrics where higher is better."""
    g, y = THRESHOLDS[metric]["green"], THRESHOLDS[metric]["yellow"]
    if value >= g:
        return "GREEN"
    if value >= y:
        return "YELLOW"
    return "RED"


def _verdict_lo(value: float, metric: str) -> str:
    """Verdict for metrics where lower is better."""
    g, y = THRESHOLDS[metric]["green"], THRESHOLDS[metric]["yellow"]
    if value <= g:
        return "GREEN"
    if value <= y:
        return "YELLOW"
    return "RED"


def generate_report(since: Optional[datetime] = None, path: Path = DB_PATH) -> dict:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    since_iso = since.isoformat()

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row

        totals = conn.execute("""
            SELECT
                COUNT(*)             AS total,
                SUM(success)         AS successful,
                COUNT(DISTINCT product_id) AS products
            FROM scrape_results WHERE timestamp >= ?
        """, (since_iso,)).fetchone()

        total     = totals["total"]     or 0
        successful = totals["successful"] or 0
        success_rate = successful / total if total > 0 else 0.0

        ban_rows = conn.execute("""
            SELECT signal_type, COUNT(*) AS cnt, MIN(timestamp) AS first_seen
            FROM ban_events
            WHERE timestamp >= ?
            GROUP BY signal_type
            ORDER BY cnt DESC
        """, (since_iso,)).fetchall()

        days_active = conn.execute("""
            SELECT COUNT(DISTINCT date(timestamp)) AS days
            FROM scrape_results WHERE timestamp >= ?
        """, (since_iso,)).fetchone()["days"] or 0

        period_days = max(1, (datetime.now(timezone.utc) - since).days)
        uptime_pct  = days_active / period_days

        total_bans = sum(r["cnt"] for r in ban_rows)
        bans_per_day = total_bans / period_days

        # Average lag: time since last successful scrape per product (in minutes)
        freshness = conn.execute("""
            SELECT AVG((julianday('now') - julianday(last_ts)) * 1440) AS lag_min
            FROM (
                SELECT MAX(timestamp) AS last_ts
                FROM scrape_results
                WHERE success = 1
                GROUP BY product_id
            )
        """).fetchone()
        avg_lag_min = round(freshness["lag_min"], 1) if freshness and freshness["lag_min"] else None

        # Latest known state per product
        current_stock = conn.execute("""
            SELECT p.name, p.brand, p.size, sr.in_stock, sr.price, sr.currency, sr.timestamp
            FROM scrape_results sr
            JOIN products p ON p.id = sr.product_id
            WHERE sr.success = 1
              AND sr.timestamp = (
                  SELECT MAX(s2.timestamp)
                  FROM scrape_results s2
                  WHERE s2.product_id = sr.product_id AND s2.success = 1
              )
            ORDER BY p.brand, p.name, p.size
        """).fetchall()

    # --- Build decision ---
    sr_v  = _verdict_hi(success_rate,  "success_rate")
    ban_v = _verdict_lo(bans_per_day,  "bans_per_day")
    up_v  = _verdict_hi(uptime_pct,    "uptime_pct")

    verdicts = [sr_v, ban_v, up_v]
    if all(v == "GREEN" for v in verdicts):
        decision = "DEVAM — Veri katmanı valide. Tüm kriterler yeşil."
    elif "RED" in verdicts:
        decision = "VAZGEÇ — Bir veya daha fazla kriter kırmızı eşiğin altında."
    else:
        decision = "GÖZLEMLE — Sınırda. Proxy veya frekans ayarı denenmeli."

    report = {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "period_start":    since_iso,
        "period_days":     period_days,
        "summary": {
            "total_requests":       total,
            "successful_requests":  successful,
            "request_success_rate": round(success_rate, 4),
            "success_rate_verdict": sr_v,
            "products_tracked":     totals["products"] or 0,
            "total_ban_events":     total_bans,
            "bans_per_day":         round(bans_per_day, 2),
            "bans_verdict":         ban_v,
            "days_active":          days_active,
            "uptime_pct":           round(uptime_pct, 4),
            "uptime_verdict":       up_v,
            "avg_data_lag_minutes": avg_lag_min,
        },
        "ban_breakdown": [dict(r) for r in ban_rows],
        "current_stock":  [dict(r) for r in current_stock],
        "thresholds_used": THRESHOLDS,
        "decision":       decision,
    }

    log.info(
        "Report | success=%.1f%% [%s]  bans/day=%.1f [%s]  uptime=%.1f%% [%s] => %s",
        success_rate * 100, sr_v,
        bans_per_day, ban_v,
        uptime_pct * 100, up_v,
        decision,
    )
    return report


def print_report(report: dict) -> None:
    s = report["summary"]
    print("\n" + "=" * 60)
    print("instock.ai — Veri Katmanı Validasyon Raporu")
    print(f"Periyot: {report['period_start']} → {report['generated_at']}")
    print("=" * 60)
    print(f"  İstek başarı oranı : {s['request_success_rate']*100:.1f}%  [{s['success_rate_verdict']}]")
    print(f"  Ban/gün            : {s['bans_per_day']:.2f}             [{s['bans_verdict']}]")
    print(f"  Uptime             : {s['uptime_pct']*100:.1f}%  [{s['uptime_verdict']}]")
    if s["avg_data_lag_minutes"] is not None:
        print(f"  Ort. veri gecikmesi: {s['avg_data_lag_minutes']:.0f} dakika")
    print("-" * 60)
    if report["ban_breakdown"]:
        print("  Ban kırılımı:")
        for row in report["ban_breakdown"]:
            print(f"    {row['signal_type']:20s}  {row['cnt']} olay  (ilk: {row['first_seen']})")
    print("-" * 60)
    print(f"  KARAR: {report['decision']}")
    print("=" * 60 + "\n")
