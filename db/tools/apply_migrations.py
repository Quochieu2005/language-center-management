"""Apply idempotent migration scripts to ONE site database from the command line (instead of SSMS in SQLCMD mode).

Safe by default: without --apply it only prints the site identity and the state of migrations 47 and 48. Connection
details come from ``SITE_DATABASES_JSON`` in ``src/api/.env`` (or the environment); credentials are never printed.

    python db/tools/apply_migrations.py --site Q7 47 48            # dry run: identity and current state
    python db/tools/apply_migrations.py --site Q7 47 48 --apply    # run the scripts, then show the state again
    python db/tools/apply_migrations.py --site Q7 47 48 --apply --backup   # take a COPY_ONLY backup first

A migration is a number (``47`` finds ``db/47_*.sql``) or a file name. Scripts run in the order given; each one is
written to be re-runnable, and 48 wraps its changes in a transaction. Only databases named ``QLTTNN_*`` are accepted.
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys

import pyodbc
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DB_DIR = os.path.join(ROOT, "db")
load_dotenv(os.path.join(ROOT, "src", "api", ".env"))


def site_config(site):
    configured = json.loads(os.environ.get("SITE_DATABASES_JSON", "{}"))
    if site not in configured:
        sys.exit(f"Site {site} is not in SITE_DATABASES_JSON (configured: {', '.join(sorted(configured)) or 'none'}).")
    return configured[site]


def connect(cfg):
    encrypt = "yes" if os.getenv("SQL_SERVER_ENCRYPT", "true").lower() in ("1", "true", "yes") else "no"
    trust = "yes" if os.getenv("SQL_SERVER_TRUST_SERVER_CERTIFICATE", "false").lower() in ("1", "true", "yes") else "no"
    auth = "Trusted_Connection=yes;" if cfg.get("trusted_connection") is True else f"UID={cfg['user']};PWD={cfg['password']};"
    cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={cfg['host']},{cfg.get('port', 1433)};DATABASE={cfg['name']};"
          f"{auth}Encrypt={encrypt};TrustServerCertificate={trust};Connection Timeout=10")
    return pyodbc.connect(cs, autocommit=True)


def resolve(token):
    if token.lower().endswith(".sql"):
        path = os.path.join(DB_DIR, token)
        matches = [path] if os.path.exists(path) else []
    else:
        matches = sorted(glob.glob(os.path.join(DB_DIR, f"{int(token):02d}_*.sql")))
    if len(matches) != 1:
        sys.exit(f"Migration '{token}' matches {len(matches)} files: {[os.path.basename(m) for m in matches]}. Use the file name.")
    return matches[0]


def batches(path):
    lines = [ln for ln in open(path, encoding="utf-8-sig").read().splitlines()
             if not ln.strip().lower().startswith(":setvar") and not re.match(r"\s*USE\s+\[\$\(DatabaseName\)\]", ln, re.I)]
    out, cur = [], []
    for ln in lines:
        if re.fullmatch(r"\s*GO\s*", ln, re.I):
            if "".join(cur).strip():
                out.append("\n".join(cur))
            cur = []
        else:
            cur.append(ln)
    if "".join(cur).strip():
        out.append("\n".join(cur))
    return out


def state(cursor):
    cursor.execute("SELECT @@SERVERNAME, DB_NAME(), CONVERT(varchar(30), SERVERPROPERTY('ProductVersion'))")
    server, db, version = cursor.fetchone()
    cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('dbo.BaiVietBlog') AND name LIKE 'anh_bia%' ORDER BY name")
    cover = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT COUNT(*) FROM sys.check_constraints WHERE name = 'CK_BaiVietBlog_anh_bia' AND is_disabled = 0 AND is_not_trusted = 0")
    cover_check = cursor.fetchone()[0] == 1
    flags = {}
    for name in ("CK_TaiKhoan_vai_tro", "CK_TaiKhoan_pham_vi"):
        cursor.execute("SELECT definition, is_disabled, is_not_trusted FROM sys.check_constraints "
                       "WHERE name = ? AND parent_object_id = OBJECT_ID('dbo.TaiKhoan')", name)
        row = cursor.fetchone()
        flags[name] = bool(row and "nguoi_dung" in row[0] and not row[1] and not row[2])
    return {
        "server": server, "database": db, "sql_server_version": version,
        "47_cover_columns": cover, "47_cover_check_enabled_and_trusted": cover_check,
        "48_vai_tro_allows_nguoi_dung": flags["CK_TaiKhoan_vai_tro"], "48_pham_vi_allows_nguoi_dung": flags["CK_TaiKhoan_pham_vi"],
    }


def backup(cursor, database):
    cursor.execute("SELECT CONVERT(nvarchar(400), SERVERPROPERTY('InstanceDefaultBackupPath'))")
    folder = cursor.fetchone()[0]
    path = folder.rstrip("\\/") + ("\\" if "\\" in folder else "/") + f"{database}_before_migration_{datetime.datetime.now():%Y%m%d_%H%M%S}.bak"
    cursor.execute(f"BACKUP DATABASE [{database}] TO DISK = N'{path}' WITH COPY_ONLY, CHECKSUM, INIT")
    while cursor.nextset():
        pass
    return os.path.basename(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", required=True, help="Site code as in SITE_DATABASES_JSON, for example Q7.")
    parser.add_argument("migrations", nargs="+", help="Migration numbers or file names, in the order to run.")
    parser.add_argument("--apply", action="store_true", help="Run the scripts. Without it only the state is shown.")
    parser.add_argument("--backup", action="store_true", help="With --apply: take a COPY_ONLY backup on the server first.")
    args = parser.parse_args()

    files = [resolve(m) for m in args.migrations]
    cfg = site_config(args.site.upper())
    if not str(cfg.get("name", "")).upper().startswith("QLTTNN_"):
        sys.exit(f"Refusing to touch database '{cfg.get('name')}': only QLTTNN_* databases are accepted.")
    try:
        conn = connect(cfg)
    except pyodbc.Error as exc:
        sys.exit(f"Cannot connect to site {args.site}: {str(exc)[:160]}")
    cursor = conn.cursor()
    print("Plan:", [os.path.basename(f) for f in files])
    print("State before:", json.dumps(state(cursor), ensure_ascii=False, indent=1))
    if not args.apply:
        print("Dry run: nothing was changed. Re-run with --apply to run the scripts.")
        return
    if args.backup:
        try:
            print("Backup taken (COPY_ONLY, CHECKSUM):", backup(cursor, cfg["name"]), "(not verified by RESTORE VERIFYONLY)")
        except pyodbc.Error as exc:
            sys.exit(f"Backup failed, nothing applied: {str(exc)[:200]}")
    for path in files:
        count = 0
        for batch in batches(path):
            cursor.execute(batch)
            while cursor.nextset():
                pass
            count += 1
        print("Applied", os.path.basename(path), f"({count} batches)")
    print("State after:", json.dumps(state(cursor), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
