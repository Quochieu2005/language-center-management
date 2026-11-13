"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, App, Button, Card, Empty, Form, Input, Modal, Space, Table, Tag, Typography } from "antd";
import { catalogApi, type SharedSubject, type SharedSubjectCreateInput, type SharedSubjectList, type SharedSubjectPatchInput } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";

type SubjectForm = { ma_mon: string; ten_mon: string; mo_ta?: string };
type SubjectWrite =
  | { kind: "create"; key: string; body: SharedSubjectCreateInput }
  | { kind: "update"; key: string; slug: string; body: SharedSubjectPatchInput }
  | { kind: "delete"; key: string; slug: string };
type PendingWrite = { operation: SubjectWrite; missingSites: string[] };

export default function SubjectsPage() {
  const { message } = App.useApp();
  const [data, setData] = useState<SharedSubjectList | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SharedSubject | null>(null);
  const [deleting, setDeleting] = useState<SharedSubject | null>(null);
  const [pending, setPending] = useState<PendingWrite | null>(null);
  const [form] = Form.useForm<SubjectForm>();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setData(await catalogApi.sharedSubjects()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được danh sách môn học từ các cơ sở."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { queueMicrotask(() => { void load(); }); }, [load]);

  const closeEditor = () => {
    setModalOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const runWrite = async (operation: SubjectWrite) => {
    setSaving(true);
    setError("");
    try {
      const result = operation.kind === "create"
        ? await catalogApi.createSubject(operation.body, operation.key)
        : operation.kind === "update"
          ? await catalogApi.updateSubject(operation.slug, operation.body, operation.key)
          : await catalogApi.deleteSubject(operation.slug, operation.key);
      if (!result.complete) {
        setPending({ operation, missingSites: result.missing_sites });
        closeEditor();
        setDeleting(null);
        message.warning("Một số cơ sở chưa xác nhận đồng bộ. Hãy dùng nút thử lại với đúng yêu cầu này.");
      } else {
        setPending(null);
        closeEditor();
        setDeleting(null);
        message.success(operation.kind === "delete" ? "Đã xóa môn học tại các cơ sở." : "Đã lưu môn học tại các cơ sở.");
      }
      await load();
    } catch (reason) {
      const uncertain = !(reason instanceof ApiError) || reason.status >= 500;
      if (uncertain) {
        setPending({ operation, missingSites: [] });
        closeEditor();
        setDeleting(null);
      } else if (operation.kind === "delete") {
        setDeleting(null);
      }
      setError(reason instanceof Error ? reason.message : "Chưa xác nhận được kết quả thao tác.");
      if (uncertain) void load();
    } finally { setSaving(false); }
  };

  const submit = (values: SubjectForm) => {
    if (!data?.complete || pending) return;
    const key = crypto.randomUUID();
    const description = values.mo_ta?.trim() || null;
    const operation: SubjectWrite = editing
      ? { kind: "update", key, slug: editing.slug, body: { ten_mon: values.ten_mon.trim(), mo_ta: description } }
      : { kind: "create", key, body: {
        ma_mon: values.ma_mon.trim().toUpperCase(),
        ten_mon: values.ten_mon.trim(), mo_ta: description,
      } };
    void runWrite(operation);
  };

  const create = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const generateSubjectCode = () => {
    const name = form.getFieldValue("ten_mon")?.trim();
    if (!name) {
      message.warning("Nhập tên môn học trước khi tạo mã.");
      return;
    }
    const words = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "D").toUpperCase().match(/[A-Z0-9]+/g) || [];
    const root = `MH-${words.map((word: string) => word[0]).join("") || "MON"}`.slice(0, 30);
    const used = new Set((data?.results || []).map((subject) => subject.ma_mon.toUpperCase()));
    let code = root;
    for (let suffix = 2; used.has(code); suffix += 1) {
      const ending = `-${suffix}`;
      code = `${root.slice(0, 30 - ending.length)}${ending}`;
    }
    form.setFieldValue("ma_mon", code);
  };

  const edit = (subject: SharedSubject) => {
    setEditing(subject);
    form.resetFields();
    form.setFieldsValue({ ten_mon: subject.ten_mon, mo_ta: subject.mo_ta || "" });
    setModalOpen(true);
  };

  const canWrite = Boolean(data?.complete && !pending && !loading && !saving);
  const columns = [
    { title: "Mã môn", dataIndex: "ma_mon", width: 140, render: (value: string) => <Typography.Text strong>{value}</Typography.Text> },
    { title: "Tên môn học", dataIndex: "ten_mon", width: 200 },
    { title: "Slug", dataIndex: "slug", width: 200 },
    { title: "Mô tả", dataIndex: "mo_ta", render: (value: string | null) => value || <Typography.Text type="secondary">Chưa có mô tả</Typography.Text> },
    { title: "Phiên bản", dataIndex: "phien_ban", width: 100 },
    { title: "Thao tác", width: 150, render: (_: unknown, row: SharedSubject) => <Space size="small">
      <Button size="small" disabled={!canWrite} onClick={() => edit(row)}>Sửa</Button>
      <Button size="small" danger disabled={!canWrite} onClick={() => setDeleting(row)}>Xóa</Button>
    </Space> },
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon title={error} />}
    {data && <>
      <Alert type={data.complete ? "info" : "warning"} showIcon title={data.complete
        ? `Danh mục được đối chiếu tại ${data.site_codes.length} cơ sở: ${data.site_codes.join(", ")}.`
        : "Danh sách chưa được đối chiếu đủ các cơ sở. Tạm khóa tạo, sửa và xóa để tránh lệch bản sao."}
        description={!data.complete ? `Site thiếu: ${data.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${data.inconsistent_sites.join(", ") || "không có"}.` : "Dữ liệu được đọc từ CSDL riêng của từng site; API chỉ tổng hợp danh sách ở tầng ứng dụng."} />
      {pending && <Alert type="warning" showIcon title="Yêu cầu đồng bộ chưa hoàn tất" description={<Space orientation="vertical">
        <span>Giữ nguyên yêu cầu và mã thao tác để tránh ghi trùng. Site chưa xác nhận: {pending.missingSites.join(", ") || "chưa xác định; cần đối soát trạng thái"}.</span>
        <Button size="small" loading={saving} onClick={() => void runWrite(pending.operation)}>Thử lại đúng yêu cầu</Button>
      </Space>} />}
    </>}
    <Card title={`Môn học dùng chung${data ? ` · ${data.count}` : ""}`} extra={<Space>
      <Button onClick={() => void load()} loading={loading}>Tải lại</Button>
      <Button type="primary" onClick={create} disabled={!canWrite}>Thêm môn học</Button>
    </Space>}>
      <Table<SharedSubject> rowKey="ma_mon" loading={loading} columns={columns} dataSource={data?.results || []}
        scroll={{ x: 900 }} pagination={{ pageSize: 10, showSizeChanger: false }}
        locale={{ emptyText: <Empty description={error ? "Không tải được dữ liệu từ các cơ sở" : "Chưa có môn học dùng chung"} /> }} />
    </Card>

    <Modal title={editing ? `Sửa môn học · ${editing.ma_mon}` : "Thêm môn học dùng chung"} open={modalOpen}
      onCancel={closeEditor} footer={null} width="min(760px, calc(100vw - 32px))"
      styles={{ body: { maxHeight: "calc(100vh - 160px)", overflowY: "auto", overflowX: "hidden" } }}>
      <Form form={form} layout="vertical" onFinish={submit}>
        {!editing && <Space size="middle" style={{ display: "flex" }} align="start">
          <Form.Item label="Mã môn học" style={{ flex: 1 }}>
            <Space.Compact style={{ width: "100%" }}>
              <Form.Item name="ma_mon" noStyle rules={[
                { required: true, message: "Nhập mã môn học." },
                { pattern: /^[A-Z0-9]+(?:-[A-Z0-9]+)*$/, message: "Chỉ dùng chữ in hoa, số và dấu gạch nối." },
                { max: 30, message: "Mã môn tối đa 30 ký tự." },
              ]}>
                <Input maxLength={30} autoComplete="off" placeholder="MH-TA" />
              </Form.Item>
              <Button htmlType="button" onClick={generateSubjectCode}>Tạo mã</Button>
            </Space.Compact>
          </Form.Item>
        </Space>}
        <Form.Item name="ten_mon" label="Tên môn học" extra="Slug được tạo tự động theo tên môn học." rules={[{ required: true, max: 100, whitespace: true }]}>
          <Input maxLength={100} placeholder="Tiếng Anh" />
        </Form.Item>
        <Form.Item name="mo_ta" label="Mô tả">
          <Input.TextArea maxLength={500} rows={4} showCount />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={saving} disabled={!canWrite}>
          {editing ? "Lưu và đồng bộ" : "Tạo và đồng bộ"}
        </Button>
      </Form>
    </Modal>

    <Modal title="Xóa môn học?" open={Boolean(deleting)} onCancel={() => setDeleting(null)}
      onOk={() => deleting && void runWrite({ kind: "delete", slug: deleting.slug, key: crypto.randomUUID() })}
      okText="Xóa môn học" cancelText="Hủy" okButtonProps={{ danger: true, loading: saving }} confirmLoading={saving}>
      <p>{deleting ? `Bạn đang xóa “${deleting.ten_mon}” (${deleting.ma_mon}) khỏi tất cả cơ sở đang hoạt động.` : ""}</p>
      <p>Nếu còn khóa học sử dụng môn này ở bất kỳ cơ sở nào, hệ thống sẽ từ chối xóa.</p>
    </Modal>
  </Space>;
}
