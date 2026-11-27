import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
API = os.path.join(ROOT, "src", "api")
os.chdir(API)
sys.path.insert(0, API)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django
django.setup()
from django.db import connections

c = connections["site_q1"].cursor()
c.execute("SELECT DB_NAME()")
db = c.fetchone()[0]
c.execute("""
SELECT t.name, c.column_id, c.name, ty.name, c.max_length, c.precision, c.scale, c.is_nullable
FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id JOIN sys.types ty ON ty.user_type_id = c.user_type_id
WHERE t.schema_id = SCHEMA_ID('dbo') ORDER BY t.name, c.column_id""")
cols = {}
for t, _i, n, ty, ml, pr, sc, nul in c.fetchall():
    cols.setdefault(t, []).append({"name": n, "type": ty, "len": ml, "prec": pr, "scale": sc, "null": bool(nul)})
c.execute("""
SELECT t.name, i.name, c.name, ic.key_ordinal FROM sys.indexes i JOIN sys.tables t ON t.object_id = i.object_id
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = ic.column_id
WHERE i.is_primary_key = 1 ORDER BY t.name, ic.key_ordinal""")
pk = {}
for t, _n, col, _o in c.fetchall():
    pk.setdefault(t, []).append(col)
c.execute("""
SELECT fk.name, tp.name, tr.name, cp.name, cr.name, fkc.constraint_column_id
FROM sys.foreign_keys fk JOIN sys.tables tp ON tp.object_id = fk.parent_object_id JOIN sys.tables tr ON tr.object_id = fk.referenced_object_id
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.columns cp ON cp.object_id = fkc.parent_object_id AND cp.column_id = fkc.parent_column_id
JOIN sys.columns cr ON cr.object_id = fkc.referenced_object_id AND cr.column_id = fkc.referenced_column_id
ORDER BY tp.name, fk.name, fkc.constraint_column_id""")
fks = {}
for name, parent, ref, pc, rc, _o in c.fetchall():
    d = fks.setdefault(name, {"name": name, "parent": parent, "ref": ref, "cols": []})
    d["cols"].append([pc, rc])

c.execute("""
SELECT t.name, i.name, c.name, ic.key_ordinal FROM sys.indexes i JOIN sys.tables t ON t.object_id = i.object_id
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = ic.column_id
WHERE i.is_unique = 1 AND i.is_primary_key = 0 AND i.has_filter = 0 ORDER BY t.name, i.name, ic.key_ordinal""")
uq = {}
for t, n, col, _o in c.fetchall():
    uq.setdefault((t, n), []).append(col)
uniques = [{"table": t, "name": n, "cols": cs} for (t, n), cs in uq.items()]
c.execute("SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID('dbo') ORDER BY name")
tables = [r[0] for r in c.fetchall()]
out = {"database": db, "tables": tables, "columns": cols, "pk": pk, "fks": list(fks.values()), "uniques": uniques}
json.dump(out, open(os.path.join(os.environ.get("TEMP", "."), "erd_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(db, len(tables), "tables;", len(fks), "foreign keys")
print(tables)
