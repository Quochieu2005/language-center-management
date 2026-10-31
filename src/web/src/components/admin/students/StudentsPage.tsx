"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Input, Popconfirm, Select, Space, Table, Tag, message } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { adminApi, type Student } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";
import { useSiteScope } from "@/lib/auth/site-scope";

export default function StudentsPage({ initialSearch }: { initialSearch: string }) {
  const { user } = useSession();
  const { siteCodes, selectedSite, setSelectedSite, loadingSites } = useSiteScope();
  const [rows, setRows] = useState<Student[]>([]);
  const [searchDraft, setSearchDraft] = useState(initialSearch);
  const [search, setSearch] = useState(initialSearch);
  const [status, setStatus] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState<string[]>([]);
  const actualSite = user?.role === "admin_big" ? selectedSite || undefined : user?.site_code || undefined;
  const load = useCallback(async () => {
    if (!actualSite) {
      setRows([]); setPartial([]);
      if (loadingSites) { setLoading(true); setError(""); }
      else { setLoading(false); setError("Chưa xác định được cơ sở cần tải học viên."); }
      return;
    }
    setLoading(true);
    try {
      const result = await adminApi.students({ site_code: actualSite, search: search.trim() || undefined, status: status === "all" ? undefined : status, limit: 100 });
      setRows(result.results); setPartial(result.missing_sites || []); setError("");
    } catch (reason) {
      setRows([]); setError(reason instanceof Error ? reason.message : "Không tải được học viên.");
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        const payload = reason.payload as unknown as { results: Student[]; missing_sites?: string[] };
        setRows(payload.results); setPartial(payload.missing_sites || []);
      }
    }
    finally { setLoading(false); }
  }, [actualSite, loadingSites, search, status]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const columns = [
    { title: "Họ tên", dataIndex: "full_name" }, { title: "Cơ sở", dataIndex: "site_code" }, { title: "Email", dataIndex: "email" },
    { title: "Điện thoại", dataIndex: "phone" }, { title: "Tình trạng", dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
    { title: "Tài khoản", dataIndex: "account_issued", render: (issued: boolean, row: Student) => issued ? <Tag color="green">Đã cấp</Tag> : user?.role === "admin_big" || user?.role === "admin_small" ? <Button size="small" onClick={async () => { try { await adminApi.issueStudentAccount(row.slug); message.success("Đã xử lý cấp tài khoản theo API."); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Không cấp được tài khoản."); } }}>Cấp tài khoản</Button> : <Tag>Chưa cấp</Tag> },
    ...(user?.role === "admin_big" || user?.role === "admin_small" ? [{ title: "Thao tác", render: (_: unknown, row: Student) => <Popconfirm title="Xóa vĩnh viễn học viên và dữ liệu liên quan?" description="Thao tác này không thể hoàn tác." okText="Xóa vĩnh viễn" okButtonProps={{ danger: true }} onConfirm={async () => { try { await adminApi.deleteStudent(row.slug, row.site_code); message.success("Đã xóa hồ sơ theo API."); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Không xóa được học viên."); } }}><Button danger size="small">Xóa</Button></Popconfirm> }] : []),
  ];
  return <Card title="Hồ sơ học viên" extra={<Space wrap><Input allowClear value={searchDraft} onChange={(e) => setSearchDraft(e.target.value)} onPressEnter={() => setSearch(searchDraft)} placeholder="Tìm tên, email, mã..." prefix={<SearchOutlined />} style={{ width: 240 }} /><Button onClick={() => setSearch(searchDraft)}>Tìm kiếm</Button></Space>}>
    <Space style={{ marginBottom: 16 }} wrap>
      {user?.role === "admin_big" && <Select value={selectedSite || undefined} onChange={setSelectedSite} loading={loadingSites} disabled={loadingSites || !siteCodes.length} style={{ width: 180 }} options={siteCodes.map((value) => ({ value, label: value }))} placeholder="Chọn cơ sở" />}
      <Select value={status} onChange={setStatus} style={{ width: 170 }} options={[{ value: "all", label: "Mọi trạng thái" }, { value: "dang_hoc", label: "Đang học" }, { value: "bao_luu", label: "Bảo lưu" }, { value: "da_chuyen_di", label: "Đã chuyển đi" }, { value: "nghi_hoc", label: "Nghỉ học" }]} />
      <Button onClick={() => { setSearch(""); setSearchDraft(""); setStatus("all"); }}>Đặt lại</Button>
    </Space>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {partial.length > 0 && <Alert type="warning" showIcon title={`Global Query thiếu site: ${partial.join(", ")}; dữ liệu chưa đầy đủ.`} style={{ marginBottom: 16 }} />}
    <Table rowKey="student_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 900 }} />
  </Card>;
}
