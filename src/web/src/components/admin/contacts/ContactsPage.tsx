"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ApiError } from "@/lib/api/client";
import { contactsApi, type ContactRequest, type ContactRequestList, type ContactRequestStatus } from "@/lib/api/contacts";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

const PAGE_SIZE = 20;
const statusLabels: Record<ContactRequestStatus, string> = {
  cho_xu_ly: "Chưa phản hồi",
  da_phan_hoi: "Đã phản hồi",
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" }).format(date);
}

export default function ContactsPage() {
  const { user } = useSession();
  const { siteCodes } = useSiteScope();
  const isAdminBig = user?.role === "admin_big";
  const [data, setData] = useState<ContactRequestList | null>(null);
  const [siteFilter, setSiteFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<ContactRequestStatus | "">("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ContactRequest | null>(null);
  const [replyOpen, setReplyOpen] = useState(false);
  const [replying, setReplying] = useState(false);
  const [replyError, setReplyError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await contactsApi.list({
        site_code: isAdminBig && siteFilter !== "all" ? siteFilter : undefined,
        status: statusFilter || undefined,
        search: search || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }));
    } catch (reason) {
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        // 503 carrying the readable part: show it with the "incomplete" warning, not a red error.
        const partial = reason.payload as unknown as ContactRequestList;
        setData({ ...partial, complete: false, missing_sites: partial.missing_sites || [] });
      } else {
        setError(reason instanceof Error ? reason.message : "Không tải được hộp thư liên hệ.");
      }
    } finally {
      setLoading(false);
    }
  }, [isAdminBig, page, search, siteFilter, statusFilter]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const openRequest = (item: ContactRequest) => {
    setSelected(item);
    setReplyError("");
    setReplyOpen(true);
  };

  const sendReply = async (values: { reply_body: string }) => {
    if (!selected) return;
    setReplying(true);
    setReplyError("");
    try {
      await contactsApi.reply(selected.site_code, selected.request_id, values.reply_body.trim());
      message.success("Email phản hồi đã được SMTP chấp nhận gửi.");
      setReplyOpen(false);
      setSelected(null);
      await load();
    } catch (reason) {
      setReplyError(reason instanceof Error ? reason.message : "Không gửi được phản hồi.");
    } finally {
      setReplying(false);
    }
  };

  const columns: ColumnsType<ContactRequest> = [
    {
      title: "Người gửi",
      dataIndex: "full_name",
      render: (_name: string, item) => <div>
        <Typography.Text strong>{item.full_name}</Typography.Text>
        <Typography.Text type="secondary" style={{ display: "block" }}>{item.email}</Typography.Text>
        {item.phone && <Typography.Text type="secondary">{item.phone}</Typography.Text>}
      </div>,
    },
    { title: "Cơ sở", dataIndex: "site_code", width: 90 },
    {
      title: "Yêu cầu",
      dataIndex: "subject",
      render: (subject: string, item) => <div>
        <Typography.Text strong>{subject}</Typography.Text>
        <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ margin: "4px 0 0" }}>{item.message}</Typography.Paragraph>
      </div>,
    },
    { title: "Trạng thái", dataIndex: "status", width: 140, render: (value: ContactRequestStatus) => <Tag color={value === "da_phan_hoi" ? "green" : "orange"}>{statusLabels[value]}</Tag> },
    { title: "Thời điểm", dataIndex: "received_at", width: 150, render: formatDate },
    {
      title: "Thao tác",
      width: 130,
      render: (_value, item) => <Button type={item.status === "cho_xu_ly" ? "primary" : "default"} onClick={() => openRequest(item)}>
        {item.status === "cho_xu_ly" ? "Xem & phản hồi" : "Xem"}
      </Button>,
    },
  ];

  return <Card title="Hộp thư liên hệ" extra={<Space wrap>
    <Input.Search
      aria-label="Tìm yêu cầu liên hệ"
      placeholder="Tên, email, tiêu đề, nội dung…"
      value={searchInput}
      onChange={(event) => setSearchInput(event.target.value)}
      onSearch={(value) => { setSearch(value.trim()); setPage(1); }}
      style={{ width: 260 }}
    />
    <Select
      aria-label="Lọc trạng thái yêu cầu liên hệ"
      value={statusFilter || "all"}
      onChange={(value: ContactRequestStatus | "all") => { setStatusFilter(value === "all" ? "" : value); setPage(1); }}
      options={[{ value: "all", label: "Mọi trạng thái" }, ...Object.entries(statusLabels).map(([value, label]) => ({ value, label }))]}
      style={{ minWidth: 150 }}
    />
    {isAdminBig && <Select
      aria-label="Lọc yêu cầu liên hệ theo cơ sở"
      value={siteFilter}
      onChange={(value: string) => { setSiteFilter(value); setPage(1); }}
      options={[{ value: "all", label: "Toàn hệ thống" }, ...siteCodes.map((site) => ({ value: site, label: site }))]}
      style={{ minWidth: 150 }}
    />}
    <Button onClick={() => void load()}>Tải lại</Button>
  </Space>}>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {data && !data.complete && <Alert
      type="warning"
      showIcon
      title={`Hộp thư chưa đầy đủ; không nhận được dữ liệu từ: ${data.missing_sites.join(", ") || "một số cơ sở"}.`}
      description="Các yêu cầu hiển thị chỉ là phần dữ liệu đã đọc được. Chọn một cơ sở cụ thể hoặc tải lại sau khi khôi phục kết nối."
      style={{ marginBottom: 16 }}
    />}
    <Table
      rowKey={(item) => `${item.site_code}:${item.request_id}`}
      loading={loading}
      columns={columns}
      dataSource={data?.results || []}
      scroll={{ x: 900 }}
      locale={{ emptyText: "Chưa có yêu cầu liên hệ phù hợp." }}
      pagination={data?.count === null ? false : {
        current: page,
        pageSize: PAGE_SIZE,
        total: data?.count || 0,
        showSizeChanger: false,
        onChange: setPage,
      }}
    />
    <Modal
      title="Yêu cầu liên hệ"
      open={replyOpen}
      onCancel={() => { if (!replying) { setReplyOpen(false); setSelected(null); } }}
      footer={null}
      destroyOnHidden
    >
      {selected && <>
        <Space orientation="vertical" size={4} style={{ width: "100%", marginBottom: 18 }}>
          <Typography.Text strong>{selected.subject}</Typography.Text>
          <Typography.Text>{selected.full_name} · {selected.email}{selected.phone ? ` · ${selected.phone}` : ""}</Typography.Text>
          <Typography.Text type="secondary">Cơ sở {selected.site_code} · {formatDate(selected.received_at)}</Typography.Text>
          <Typography.Paragraph style={{ margin: "10px 0 0", whiteSpace: "pre-wrap" }}>{selected.message}</Typography.Paragraph>
        </Space>
        {selected.reply_body && <Alert
          type="success"
          showIcon
          title="Phản hồi đã gửi"
          description={<><Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 4 }}>{selected.reply_body}</Typography.Paragraph><Typography.Text type="secondary">{selected.replied_at ? formatDate(selected.replied_at) : ""}</Typography.Text></>}
          style={{ marginBottom: 16 }}
        />}
        {selected.status === "cho_xu_ly" ? <>
          <Typography.Paragraph type="secondary">Phản hồi sẽ được gửi đến email người gửi qua SMTP đã cấu hình.</Typography.Paragraph>
          {replyError && <Alert type="error" showIcon title={replyError} style={{ marginBottom: 12 }} />}
          <Form layout="vertical" onFinish={sendReply}>
            <Form.Item name="reply_body" label="Nội dung phản hồi" rules={[{ required: true, whitespace: true }, { max: 5000 }]}>
              <Input.TextArea rows={6} maxLength={5000} showCount />
            </Form.Item>
            <Space style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button onClick={() => setReplyOpen(false)} disabled={replying}>Hủy</Button>
              <Button type="primary" htmlType="submit" loading={replying}>Gửi phản hồi</Button>
            </Space>
          </Form>
        </> : <Alert type="info" showIcon title="Yêu cầu này đã được phản hồi." />}
      </>}
    </Modal>
  </Card>;
}
