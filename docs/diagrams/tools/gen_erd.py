"""Generate the ERD as Mermaid flowcharts (pointed arrows, parent -> child) from the real Q1 metadata so it cannot drift."""
import json, os

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
M = json.load(open(os.path.join(os.environ["TEMP"], "erd_meta.json"), encoding="utf-8"))
COLS = {t: {c["name"]: c for c in cs} for t, cs in M["columns"].items()}
PK = M["pk"]

KIND = {"NB": "nhân bản", "MN": "mảnh nguyên thủy", "DX": "mảnh dẫn xuất", "CT": "cục bộ", "CB": "chỉ authority"}
KIND_OF = {}
for kind, names in {
    "NB": "CoSo MonHoc KhoaHoc TaiKhoan DanhMucBlog BaiVietBlog",
    "MN": "HocVien GiaoVien NhanVien Admin PhongHoc LopHoc YeuCauLienHe",
    "DX": "BuoiHoc DangKy DiemDanh HocPhi DotHocPhi PhieuThu Diem",
    "CT": "GiaoDichChuyenCoSo LichSuChuyenCoSo ThongBao Logs YeuCauThanhToan SuKienThanhToan",
    "CB": "PhienDangNhap TokenDatLaiMatKhau GiaoDichDatLaiMatKhau DatChoEmailHocVien TrangThaiKhoEmail DongBoTaiKhoan NguoiDung",
}.items():
    for n in names.split():
        KIND_OF[n] = kind

EXTRA = {  # readable non-key columns worth showing (must exist in the real schema)
    "*": ["ma_co_so", "trang_thai", "slug"],
    "TaiKhoan": ["vai_tro", "email", "phien_ban"],
    "LopHoc": ["si_so_toi_da", "si_so_hien_tai"],
    "HocPhi": ["so_tien_phai_dong", "so_tien_da_dong"],
    "KhoaHoc": ["hoc_phi_chuan", "phien_ban"],
    "MonHoc": ["phien_ban"],
    "HocVien": ["ho_ten"],
    "Diem": ["loai_diem", "diem_so"],
    "PhieuThu": ["loai", "so_tien"],
}


def ty(name, table):
    t = COLS[table][name]["type"]
    if t in ("varchar", "nvarchar", "char", "nchar", "uniqueidentifier"):
        return "string"
    if t in ("int", "bigint", "smallint", "tinyint"):
        return "int"
    if t in ("decimal", "numeric", "float", "money"):
        return "decimal"
    if t == "bit":
        return "bool"
    if t.startswith("date") or t == "time":
        return "datetime"
    return "string"


def fk_set(tables):
    return [f for f in M["fks"] if f["parent"] in tables and f["ref"] in tables]


def node(table, tables, stubs):
    fks_here = [f for f in M["fks"] if f["parent"] == table and f["ref"] in tables]
    fkcols = {pc for f in fks_here for pc, _ in f["cols"]}
    show = list(PK.get(table, []))
    if table not in stubs:
        for c in (c["name"] for c in M["columns"][table]):
            if c in fkcols and c not in show:
                show.append(c)
        for c in EXTRA["*"] + EXTRA.get(table, []):
            if c in COLS[table] and c not in show:
                show.append(c)
    single_unique = {u["cols"][0] for u in M["uniques"] if u["table"] == table and len(u["cols"]) == 1}
    rows = []
    for c in show:
        keys = []
        if c in PK.get(table, []):
            keys.append("PK")
        if c in fkcols:
            keys.append("FK")
        if c in single_unique and "PK" not in keys:
            keys.append("UK")
        rows.append((", ".join(keys) + " " if keys else "") + f"{c} : {ty(c, table)}")
    kind = KIND[KIND_OF[table]] if table in KIND_OF else ""
    head = f"<b>{table}</b>" + (f"<br/><i>{kind}</i>" if kind else "")
    body = "<br/>".join(rows)
    return f'    {table}["{head}<br/>──────────<br/>{body}"]:::{KIND_OF.get(table, "NB")}'


def edge(f):
    child = f["parent"]
    cols = [pc for pc, _ in f["cols"]]
    non_site = [c for c in cols if c != "ma_co_so"]
    if not non_site:  # the FK is on ma_co_so itself (e.g. TaiKhoan.ma_co_so, nullable for admin_big and nguoi_dung)
        non_site = cols
    nullable = any(COLS[child][c]["null"] for c in non_site)
    uniq = False
    for u in M["uniques"]:
        if u["table"] != child:
            continue
        ucols = [c for c in u["cols"] if c != "ma_co_so"]
        if set(ucols) == set(non_site) and non_site:
            uniq = True
    left = "0..1" if nullable else "1"
    right = "0..1" if uniq else "0..n"
    composite = "ma_co_so" in cols and any(c != "ma_co_so" for c in cols)
    label = " + ".join(non_site) + (" (cùng ma_co_so)" if composite else "")
    # parent --> child: the arrowhead points at the table that holds the foreign key
    return f'    {f["ref"]} -->|"{label}<br/>{left} : {right}"| {child}'


def diagram(tables, stubs=()):
    stubs = set(stubs)
    parts = ["%%elk", "flowchart TB"]
    parts += [node(t, tables, stubs) for t in tables]
    rels = sorted({edge(f) for f in fk_set(tables)})
    classes = [
        "    classDef NB fill:#12263f,stroke:#3b82f6,color:#e5eefc,stroke-width:1.5px",
        "    classDef MN fill:#10281c,stroke:#22c55e,color:#e3f6ea,stroke-width:1.5px",
        "    classDef DX fill:#1c2a12,stroke:#84cc16,color:#eef7dc,stroke-width:1.5px",
        "    classDef CT fill:#2e2410,stroke:#f59e0b,color:#fbf0d6,stroke-width:1.5px",
        "    classDef CB fill:#2f1220,stroke:#ec4899,color:#fbe3ee,stroke-width:1.5px",
    ]
    return "\n".join(parts + rels + classes) + "\n"


BUSINESS = ["CoSo", "MonHoc", "KhoaHoc", "TaiKhoan", "HocVien", "GiaoVien", "NhanVien", "Admin", "PhongHoc", "LopHoc",
            "BuoiHoc", "DangKy", "HocPhi", "DotHocPhi", "PhieuThu", "Diem", "DiemDanh"]
# DongBoTaiKhoan, DatChoEmailHocVien and Logs have no foreign keys by design, so they are not drawn (they would float alone).
SETS = [
    ("erd-nghiep-vu", BUSINESS, ()),
    ("erd-chuyen-co-so", ["CoSo", "HocVien", "GiaoDichChuyenCoSo", "LichSuChuyenCoSo"], ("CoSo", "HocVien")),
    ("erd-xac-thuc", ["CoSo", "TaiKhoan", "HocVien", "PhienDangNhap", "TokenDatLaiMatKhau", "GiaoDichDatLaiMatKhau", "NguoiDung"], ("CoSo", "HocVien")),
    ("erd-phu-tro", ["CoSo", "TaiKhoan", "HocPhi", "ThongBao", "YeuCauLienHe", "YeuCauThanhToan", "SuKienThanhToan", "DanhMucBlog", "BaiVietBlog"],
     ("CoSo", "TaiKhoan", "HocPhi")),
]
for name, tabs, stubs in SETS:
    missing = [t for t in tabs if t not in M["columns"]]
    assert not missing, missing
    text = diagram(tabs, stubs)
    open(os.path.join(OUT, name + ".mmd"), "w", encoding="utf-8").write(text)
    print(name, len(text.splitlines()), "lines;", sum(1 for l in text.splitlines() if "-->" in l), "relationships")
