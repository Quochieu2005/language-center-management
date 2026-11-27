"""TC-DTX-01 qua code ứng dụng: gọi execute_approved_transfer của source với cấu hình 2PC, trên hai instance tạm.

Dựng lại database tạm bằng ev_dtx (build + fixture), rồi chạy service chuyển cơ sở thật của Django. Ghi kết quả vào
docs/evidence/TC-DTX-01/<ngày>/ung-dung.json. Cần MS DTC đang chạy và instance thứ hai (xem ev_dtx.py).
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ev_dtx as d  # noqa: E402  (đọc cấu hình Q1 từ src/api/.env để biết máy chủ chính)

d.build()
d.fixture()

ports = [str(r[0]).replace(chr(0), "").strip() for r in d.q(
    d.INSTANCE2, "master",
    "SELECT value_data FROM sys.dm_server_registry WHERE value_name IN ('TcpDynamicPorts','TcpPort')")]
port2 = next(p for p in ports if p.isdigit() and int(p) > 0)
os.environ["SITE_DATABASES_JSON"] = json.dumps({
    "EVA": {"name": d.DBA, "host": d.h.HOST, "port": int(d.h.PORT), "trusted_connection": True},
    "EVB": {"name": d.DBB, "host": "[::1]", "port": int(port2), "trusted_connection": True},
})
os.environ["AUTH_SESSION_SITE_CODE"] = "EVA"
os.environ["SITE_UNREACHABLE_COOLDOWN_SECONDS"] = "0"
os.environ["TRANSFER_2PC_LINKED_SERVERS_JSON"] = json.dumps({"EVA": {"EVB": "LS_EVB"}})
os.chdir(d.h.API)
sys.path.insert(0, d.h.API)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django  # noqa: E402

django.setup()
from core.academics.common import AcademicConflict  # noqa: E402
from core.academics.transfers import execute_approved_transfer  # noqa: E402

result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
          "note": "execute_approved_transfer của source, nguồn EVA (SQL Server 2022) và đích EVB (SQL Server 2025), TRANSFER_2PC_LINKED_SERVERS_JSON={EVA:{EVB:LS_EVB}}"}

# 1. đường 2PC qua service
d.new_transfer("EVA-CC-000001", "EVA-HV-000002", d.main_server(), d.DBA, "EVA", "EVB")
before = d.snapshot("EVA-HV-000002", "EVA-CC-000001")
res = execute_approved_transfer(source_site="EVA", transfer_id="EVA-CC-000001", actor_id=d.ACTOR)
after = d.snapshot("EVA-HV-000002", "EVA-CC-000001")
result["1_service_2pc"] = {"truoc": before, "ket_qua_tra_ve": res, "sau": after}

# 2. gọi lại giao dịch đã hoàn tất: không chạy lại, không tạo hồ sơ lần hai
res2 = execute_approved_transfer(source_site="EVA", transfer_id="EVA-CC-000001", actor_id=d.ACTOR)
result["2_goi_lai"] = {"ket_qua_tra_ve": res2,
                       "so_ho_so_dich": d.q(d.INSTANCE2, d.DBB, "SELECT COUNT(*) FROM dbo.HocVien WHERE ma_hoc_vien='EVA-HV-000002'")[0][0]}

# 3. đích từ chối ⇒ AcademicConflict (không phải lỗi hạ tầng) và nguồn nguyên vẹn
d.new_transfer("EVA-CC-000002", "EVA-HV-000003", d.main_server(), d.DBA, "EVA", "EVB")
d.q(d.INSTANCE2, d.DBB, "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) "
                         "VALUES ('EVA-HV-000003','xung-dot','EVB','EVB',N'Hồ sơ khác', CONVERT(date,SYSUTCDATETIME()), 'dang_hoc')")
before = d.snapshot("EVA-HV-000003", "EVA-CC-000002")
try:
    execute_approved_transfer(source_site="EVA", transfer_id="EVA-CC-000002", actor_id=d.ACTOR)
    outcome = "không lỗi (sai)"
except AcademicConflict as exc:
    outcome = "AcademicConflict: " + str(exc)[:120]
after = d.snapshot("EVA-HV-000003", "EVA-CC-000002")
result["3_dich_tu_choi"] = {"ket_qua": outcome, "nguon_nguyen_ven": before["nguon_EVA"] == after["nguon_EVA"]}

result["ket_luan"] = {
    "service_2pc": bool(res.get("complete") and res.get("mechanism") == "2PC"
                        and after is not None and result["1_service_2pc"]["sau"]["nguon_EVA"]["hoc_vien"][0][0] == "da_chuyen_di"
                        and result["1_service_2pc"]["sau"]["dich_EVB"]["hoc_vien"][0][0] == "dang_hoc"),
    "goi_lai_khong_lap": bool(res2.get("complete") and result["2_goi_lai"]["so_ho_so_dich"] == 1),
    "dich_tu_choi_la_conflict": bool(outcome.startswith("AcademicConflict") and result["3_dich_tu_choi"]["nguon_nguyen_ven"]),
}
out = os.path.join(d.OUT, "ung-dung.json")
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
print(json.dumps(result["ket_luan"], ensure_ascii=False))
print(outcome)
