"""Scratch-DB harness: two throwaway site databases (QLTTNN_EVA, QLTTNN_EVB) on the Q1 instance.

Never touches QLTTNN_Q1/Q7/TD. Credentials are read from src/api/.env and never printed.
"""
import json
import os
import re
import sys

import pyodbc
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
API = os.path.join(ROOT, "src", "api")
DB = os.path.join(ROOT, "db")
load_dotenv(os.path.join(API, ".env"))

_q1 = json.loads(os.environ["SITE_DATABASES_JSON"])["Q1"]
HOST, PORT = _q1["host"], str(_q1.get("port", 1433))
assert _q1.get("trusted_connection") is True
SITES = {"EVA": "QLTTNN_EVA", "EVB": "QLTTNN_EVB"}


def connect(database="master", autocommit=True):
    cs = (
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=%s,%s;DATABASE=%s;Trusted_Connection=yes;"
        "Encrypt=%s;TrustServerCertificate=%s;Connection Timeout=5"
        % (HOST, PORT, database,
           "yes" if os.getenv("SQL_SERVER_ENCRYPT", "true").lower() in ("1", "true", "yes") else "no",
           "yes" if os.getenv("SQL_SERVER_TRUST_SERVER_CERTIFICATE", "false").lower() in ("1", "true", "yes") else "no")
    )
    return pyodbc.connect(cs, autocommit=autocommit)


def batches(path):
    text = open(path, encoding="utf-8-sig").read()
    lines = [ln for ln in text.splitlines()
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


def run_script(database, filename):
    conn = connect(database)
    cur = conn.cursor()
    n = 0
    for b in batches(os.path.join(DB, filename)):
        cur.execute(b)
        while cur.nextset():
            pass
        n += 1
    conn.close()
    return n


def create_databases():
    conn = connect("master")
    cur = conn.cursor()
    for name in SITES.values():
        cur.execute("IF DB_ID(?) IS NOT NULL BEGIN ALTER DATABASE [%s] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [%s]; END" % (name, name), name)
        cur.execute("CREATE DATABASE [%s]" % name)
    conn.close()


def drop_databases():
    conn = connect("master")
    cur = conn.cursor()
    for name in SITES.values():
        cur.execute("IF DB_ID(?) IS NOT NULL BEGIN ALTER DATABASE [%s] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [%s]; END" % (name, name), name)
    conn.close()


def scratch_sites_json(extra=None):
    cfg = {code: {"name": name, "host": HOST, "port": int(PORT), "trusted_connection": True}
           for code, name in SITES.items()}
    cfg.update(extra or {})
    return json.dumps(cfg)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "create":
        create_databases()
        print("created", list(SITES.values()))
    elif cmd == "drop":
        drop_databases()
        print("dropped", list(SITES.values()))
    elif cmd == "script":
        for code, name in SITES.items():
            print(code, sys.argv[2], "batches:", run_script(name, sys.argv[2]))
