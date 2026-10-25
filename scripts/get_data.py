"""Download the Portal BASE contract files (IMPIC, dados.gov.pt) and convert them to Parquet.

    python scripts/get_data.py                 # 2019-2026
    python scripts/get_data.py --years 2024 2025
    python scripts/get_data.py --skip-download # convert xlsx already in data/xlsx/

Source: dataset 66d72d488ca4b7cb2de28712, "Contratos Públicos - Portal BASE - IMPIC - Contratos de 2012 a 2026",
one workbook per year (contratosYYYY.xlsx, sheet Sheet1). The resource URLs carry a timestamp that changes on
every republication, so the script looks them up through the dados.gov.pt API instead of hard-coding them.

Every column is read as text (all_varchar) and written unchanged; parsing happens in the dbt staging models.
Output: data/raw/contratos_YYYY.parquet (zstd). Needs duckdb >= 1.1 (read_xlsx from the excel extension).

The files in this repository were downloaded on 2026-10-25 on a Windows machine; the container used to build
the project had no route to dados.gov.pt. The script itself runs anywhere with Python and internet access.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

import duckdb

DATASET_ID = "66d72d488ca4b7cb2de28712"
API_URL = f"https://dados.gov.pt/api/1/datasets/{DATASET_ID}/"
ROOT = Path(__file__).resolve().parents[1]
XLSX_DIR = ROOT / "data" / "xlsx"
RAW_DIR = ROOT / "data" / "raw"
USER_AGENT = "public-procurement-pt/1.0 (portfolio project; python urllib)"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def resource_urls(years: list[int]) -> dict[int, str]:
    """Map year -> download URL of contratosYYYY.xlsx, from the dataset's resource list."""
    data = fetch_json(API_URL)
    found: dict[int, str] = {}
    for res in data.get("resources", []):
        name = (res.get("title") or "") + " " + (res.get("url") or "")
        m = re.search(r"contratos(\d{4})\.xlsx", name, re.IGNORECASE)
        if m and int(m.group(1)) in years:
            found[int(m.group(1))] = res["url"]
    missing = sorted(set(years) - set(found))
    if missing:
        sys.exit(f"No contratosYYYY.xlsx resource found for {missing} at {API_URL}")
    return found


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    tmp.replace(target)


def convert(xlsx: Path, parquet: Path, con: duckdb.DuckDBPyConnection) -> int:
    parquet.parent.mkdir(parents=True, exist_ok=True)
    src = str(xlsx).replace("'", "''")
    dst = str(parquet).replace("'", "''")
    con.execute(
        f"COPY (SELECT * FROM read_xlsx('{src}', sheet='Sheet1', all_varchar=true)) "
        f"TO '{dst}' (FORMAT parquet, COMPRESSION zstd)"
    )
    return con.execute(f"SELECT count(*) FROM read_parquet('{dst}')").fetchone()[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", type=int, nargs="+", default=list(range(2019, 2027)))
    ap.add_argument("--skip-download", action="store_true", help="convert files already in data/xlsx/")
    args = ap.parse_args()

    if not args.skip_download:
        urls = resource_urls(args.years)
        for year in args.years:
            target = XLSX_DIR / f"contratos{year}.xlsx"
            print(f"download {year}: {urls[year]}")
            download(urls[year], target)

    con = duckdb.connect()
    con.execute("INSTALL excel; LOAD excel;")
    for year in args.years:
        xlsx = XLSX_DIR / f"contratos{year}.xlsx"
        if not xlsx.exists():
            sys.exit(f"missing {xlsx}")
        rows = convert(xlsx, RAW_DIR / f"contratos_{year}.parquet", con)
        print(f"{year}: {rows:,} rows -> data/raw/contratos_{year}.parquet")


if __name__ == "__main__":
    main()
