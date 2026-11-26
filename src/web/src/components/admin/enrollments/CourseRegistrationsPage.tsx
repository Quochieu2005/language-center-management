"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, App, Button, Card, Input, Select, Space, Switch, Table, Tag, Tooltip, Typography } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { adminApi, type CourseRegistration } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";

const when = new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" });

/** People who registered for a course; staff create their login (and password) from here. */
export default function CourseRegistrationsPage() {
  const { message, modal } = App.useApp();
  const { user } = useSession();
  const { siteCodes, selectedSite, setSelectedSite, loadingSites } = useSiteScope();
  const [rows, setRows] = useState<CourseRegistration[]>([]);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [pendingOnly, setPendingOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState<string[]>([]);
  const [issuing, setIssuing] = useState("");
  const isAdminBig = user?.role === "admin_big";
  const canIssue = isAdminBig || user?.role === "admin_small";
  const site = isAdminBig ? selectedSite || undefined : user?.site_code || undefined;
  const requestedSite = site === ALL_SITES ? undefined : site;

  const load = useCallback(async () => {
    if (!site) {
      setRows([]); setPartial([]);
      if (loadingSites) { setLoading(true); setError(""); }
      else { setLoading(false); setError("Chưa xác định được cơ sở cần tải."); }
      return;
    }
    setLoading(true);
    try {
      const result = await adminApi.courseRegistrations({
        site_code: isAdminBig ? requestedSite : undefined, pending: pendingOnly, search: search.trim() || undefined, limit: 100,
      });
      setRows(result.results); setPartial(result.missing_sites || []); setError("");
    } catch (reason) {
      setRows([]); setError(reason instanceof Error ? reason.message : "Không tải được danh sách đăng ký.");
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        const payload = reason.payload as unknown as { results: CourseRegistration[]; missing_sites?: string[] };
        setRows(payload.results); setPartial(payload.missing_sites || []);
      }
    } finally { setLoading(false); }
  }, [isAdminBig, loadingSites, pendingOnly, requestedSite, search, site]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const issue = (row: CourseRegistration) => modal.confirm({
    title: `Cấp tài khoản cho ${row.full_name}?`,
    content: row.has_website_account
      ? "Người này đã đăng ký tài khoản trên website. Tài khoản đó sẽ được chuyển thành tài khoản học viên và giữ nguyên mật khẩu của họ."
      : "Hệ thống tạo tài khoản học viên bằng email đăng ký, cấp mật khẩu tạm và gửi qua email; người học phải đổi mật khẩu ở lần đăng nhập đầu.",
    okText: "Cấp tài khoản", cancelText: "Hủy",
    onOk: async () => {
      setIssuing(row.slug);
      try {
        const result = await adminApi.issueStudentAccount(row.slug, isAdminBig ? row.site_code : undefined);
        message.success(result.email_sent ? "Đã cấp tài khoản và gửi mật khẩu qua email." : "Đã gắn tài khoản xem web vào hồ sơ học viên.");
        if (!result.replication_complete) message.warning(`Đang chờ đồng bộ tài khoản: ${result.replication_pending_sites.join(", ")}.`);
        void load();
      } catch (reason) {
        message.error(reason instanceof Error ? reason.message : "Không cấp được tài khoản.");
      } finally { setIssuing(""); }
    },
  });

  const columns: ColumnsType<CourseRegistration> = [
    { title: "Ngày đăng ký", dataIndex: "enrolled_at", width: 150, render: (value: string) => when.format(new Date(value)) },
    {
      title: "Người đăng ký", dataIndex: "full_name",
      render: (_: unknown, row) => <div><strong>{row.full_name}</strong><div><Typography.Text type="secondary">{row.email || "Chưa có email"}{row.phone ? ` · ${row.phone}` : ""}</Typography.Text></div></div>,
    },
    { title: "Khóa học / lớp", render: (_: unknown, row) => <div>{row.course_name}<div><Typography.Text type="secondary">{row.class_name}</Typography.Text></div></div> },
    { title: "Cơ sở", dataIndex: "site_code", width: 80 },
    {
      title: "Tài khoản", width: 190,
      render: (_: unknown, row) => row.account_issued
        ? <Tag color="green">Đã cấp</Tag>
        : <Space orientation="vertical" size={4}>
          {row.has_website_account ? <Tag color="blue">Đã đăng ký trên website</Tag> : <Tag>Chưa có tài khoản</Tag>}
          {canIssue
            ? <Tooltip title={row.account_issue_eligible ? undefined : "Chỉ cấp tài khoản cho hồ sơ đang học có email hợp lệ."}>
              <span><Button size="small" type="primary" disabled={!row.account_issue_eligible} loading={issuing === row.slug} onClick={() => issue(row)}>Cấp tài khoản</Button></span>
            </Tooltip>
            : <Typography.Text type="secondary">Chờ Admin cấp tài khoản</Typography.Text>}
        </Space>,
    },
  ];

  return <Card title="Đăng ký khóa học" extra={<Space wrap>
    <Input allowClear value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} onPressEnter={() => setSearch(searchDraft)} placeholder="Tìm tên, email, khóa học..." prefix={<SearchOutlined />} style={{ width: 240 }} />
    <Button onClick={() => setSearch(searchDraft)}>Tìm kiếm</Button>
  </Space>}>
    <Space style={{ marginBottom: 16 }} wrap>
      {isAdminBig && <Select value={site} onChange={setSelectedSite} loading={loadingSites} disabled={loadingSites} style={{ width: 180 }} options={[{ value: ALL_SITES, label: "Toàn hệ thống" }, ...siteCodes.map((value) => ({ value, label: value }))]} />}
      <Space size={8}><Switch checked={pendingOnly} onChange={setPendingOnly} /><span>Chỉ người chưa có tài khoản học viên</span></Space>
      <Button onClick={() => { setSearch(""); setSearchDraft(""); setPendingOnly(true); }}>Đặt lại</Button>
    </Space>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {partial.length > 0 && <Alert type="warning" showIcon title={`Chưa lấy được dữ liệu của cơ sở ${partial.join(", ")} (đang ngoại tuyến). Danh sách dưới đây chỉ gồm các cơ sở còn lại.`} style={{ marginBottom: 16 }} />}
    <Table rowKey="enrollment_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 860 }}
      locale={{ emptyText: pendingOnly ? "Chưa có ai đăng ký khóa học đang chờ cấp tài khoản." : "Chưa có đăng ký khóa học nào." }} />
  </Card>;
}
