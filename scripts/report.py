#!/usr/bin/env python3
"""
Manuel rapor üret ve terminale bas.
Kullanım: python scripts/report.py [--days N]
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reporter.summary import generate_report, print_report

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=7, help="Kaç günlük veri analiz edilsin")
args = parser.parse_args()

since = datetime.now(timezone.utc) - timedelta(days=args.days)
report = generate_report(since=since)
print_report(report)
