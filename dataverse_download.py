#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional, Tuple
               
import requests


def sanitize_dirlabel(s: str) -> str:
    s = s.strip().strip("/").strip()
    if not s:
        return ""
    # make it filesystem-safe
    s = s.replace("\\", "_")
    s = re.sub(r"[/:]+", "_", s)
    s = re.sub(r"\s+", "_", s)
    return s


def http_get_json(url: str, headers: dict, timeout: int) -> dict:
    r = requests.get(url, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"GET {url} -> {r.status_code}\n{r.text[:400]}")
    return r.json()


def http_download(url: str, headers: dict, outpath: Path, timeout: int, overwrite: bool) -> Tuple[int, int]:
    outpath.parent.mkdir(parents=True, exist_ok=True)
    if outpath.exists() and outpath.stat().st_size > 0 and not overwrite:
        return 200, outpath.stat().st_size

    with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
        status = r.status_code
        if status != 200:
            # write response text for debugging if any
            try:
                text = r.text
            except Exception:
                text = ""
            raise RuntimeError(f"GET {url} -> {status}\n{text[:400]}")

        tmp = outpath.with_suffix(outpath.suffix + ".part")
        n = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    n += len(chunk)
        os.replace(tmp, outpath)
        return status, n


def iter_csv_files(ds_json: dict) -> Iterable[Tuple[str, str, Optional[str], str]]:
    """
    yields: (dirlabel, filename, file_persistent_id, file_numeric_id)
    """
    files = ds_json["data"]["latestVersion"]["files"]
    for f in files:
        df = f.get("dataFile", {})
        fn = df.get("filename", "")
        if not fn.lower().endswith(".csv"):
            continue
        dirlabel = f.get("directoryLabel") or ""
        filepid = df.get("persistentId")
        fileid = str(df.get("id"))
        yield dirlabel, fn, filepid, fileid


def main() -> int:
    ap = argparse.ArgumentParser(description="Download CSV files only from a Dataverse dataset (latest version).")
    ap.add_argument("--base", default="https://dataverse.geus.dk", help="Dataverse base URL")
    ap.add_argument("--pid", required=True, help="Dataset persistentId, e.g. doi:10.22008/FK2/IW73UU")
    ap.add_argument("--outroot", required=True, help="Output root folder, e.g. /mnt/ice/.../dataverse")
    ap.add_argument("--min-csv", type=int, default=30, help="Minimum expected CSV count (sanity check)")
    ap.add_argument("--token", default=os.environ.get("DATAVERSE_TOKEN", ""), help="Dataverse API token (optional)")
    ap.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = ap.parse_args()

    headers = {}
    if args.token:
        headers["X-Dataverse-key"] = args.token

    base = args.base.rstrip("/")
    pid = args.pid

    # resolve latest version number
    ds_url = f"{base}/api/datasets/:persistentId?persistentId={pid}"
    if args.verbose:
        print(f"[INFO] Fetch dataset JSON: {ds_url}", file=sys.stderr)
    ds = http_get_json(ds_url, headers=headers, timeout=args.timeout)

    ver_major = ds["data"]["latestVersion"]["versionNumber"]
    ver_minor = ds["data"]["latestVersion"].get("versionMinorNumber", 0)
    version_folder = f"V{ver_major}"
    target_dir = Path(args.outroot) / version_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"[INFO] Latest version: {ver_major}.{ver_minor} -> {target_dir}", file=sys.stderr)

    # enumerate csv files
    rows = list(iter_csv_files(ds))
    if args.verbose:
        print(f"[INFO] CSV entries in latestVersion: {len(rows)}", file=sys.stderr)
    if not rows:
        print("[ERROR] No CSV files found in latestVersion.files", file=sys.stderr)
        return 2

    ok = 0
    for i, (dirlabel, filename, filepid, fileid) in enumerate(rows, start=1):
        safe = sanitize_dirlabel(dirlabel)
        outdir = target_dir / safe if safe else target_dir
        outpath = outdir / filename

        if args.verbose:
            print(f"[{i}/{len(rows)}] {filename}", file=sys.stderr)
            print(f"  dirlabel={dirlabel}", file=sys.stderr)
            print(f"  outpath={outpath}", file=sys.stderr)

        try:
            if filepid:
                # use persistentId endpoint (URL-encode via params)
                url = f"{base}/api/access/datafile/:persistentId"
                params = {"persistentId": filepid}
                # requests will encode params properly
                prep = requests.Request("GET", url, params=params).prepare()
                dl_url = prep.url

                def ensure_file_path(p: Path):
                    if p.exists() and p.is_dir():
                        shutil.rmtree(p)

                # in the loop, right before http_download(...):
                ensure_file_path(outpath)
                tmp = outpath.with_suffix(outpath.suffix + ".part")
                ensure_file_path(tmp)
                status, nbytes = http_download(dl_url, headers=headers, outpath=outpath, timeout=args.timeout, overwrite=args.overwrite)
            else:
                # fallback to numeric id endpoint
                dl_url = f"{base}/api/access/datafile/{fileid}"
                status, nbytes = http_download(dl_url, headers=headers, outpath=outpath, timeout=args.timeout, overwrite=args.overwrite)

            ok += 1
            if args.verbose:
                print(f"  -> OK ({nbytes} bytes)", file=sys.stderr)

        except Exception as e:
            print(f"[ERROR] Download failed for {filename}", file=sys.stderr)
            print(f"  filepid={filepid} fileid={fileid} dirlabel={dirlabel}", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            return 3

    # sanity check
    csv_count = sum(1 for _ in target_dir.rglob("*.csv"))
    print(f"[DONE] Downloaded {ok}/{len(rows)} CSVs into {target_dir} (found {csv_count} *.csv)")
    if csv_count <= args.min_csv:
        print(f"[ERROR] Sanity check failed: only {csv_count} CSVs (<= {args.min_csv})", file=sys.stderr)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
