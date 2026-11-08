"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Empty, Form, Input, InputNumber, Modal, Popconfirm, Space, Table, Tag, message } from "antd";
import { catalogApi, type PublicCourse, type PublicCourseList, type SharedCourseCreateInput, type SharedCoursePatchInput } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";

type CourseForm = {
  ma_khoa_hoc?: string;
  slug?: string;
  ma_mon: string;
  ten_khoa_hoc: string;
  trinh_do: string;
  so_buoi: number;
  hoc_phi_chuan: number;
};
type PendingWrite =
  | { kind: "create"; key: string; body: SharedCourseCreateInput }
  | { kind: "update"; key: string; slug: string; body: SharedCoursePatchInput }
  | { kind: "delete"; key: string; slug: string };
type PendingSync = { operation: PendingWrite; missingSites: string[] };

const money = new Intl.NumberFormat("vi-VN");

export default function CoursesPage() {
  const [catalog, setCatalog] = useState<PublicCourseList | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<PublicCourse | null>(null);
  const [pending, setPending] = useState<PendingSync | null>(null);
  const [form] = Form.useForm<CourseForm>();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setCatalog(await catalogApi.publicCourses()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được danh mục khóa học."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { queueMicrotask(() => { void load(); }); }, [load]);

  const runWrite = async (operation: PendingWrite) => {
    setSaving(true);
    setError("");
    try {
      const result = operation.kind === "create"
        ? await catalogApi.createCourse(operation.body, operation.key)
        : operation.kind === "update"
          ? await catalogApi.updateCourse(operation.slug, operation.body, operation.key)
          : await catalogApi.deleteCourse(operation.slug, operation.key);
      if (!result.complete) {
        setPending({ operation, missingSites: result.missing_sites });
        setModal(false);
        form.resetFields();
        message.warning("Một số cơ sở chưa đồng bộ. Dùng nút thử lại bên dưới để tiếp tục cùng yêu cầu.");
        void load();
        return;
      }
      setPending(null);
      setModal(false);
      setEditing(null);
      form.resetFields();
      message.success(operation.kind === "delete" ? "Đã xóa khóa học trên các cơ sở." : "Đã đồng bộ khóa học trên các cơ sở.");
      await load();
    } catch (reason) {
      if (!(reason instanceof ApiError) || reason.status >= 500) setPending({ operation, missingSites: [] });
      else setPending(null);
      setError(reason instanceof Error ? reason.message : "Chưa xác nhận được kết quả. Hãy thử lại cùng yêu cầu.");
      if (!(reason instanceof ApiError) || reason.status >= 500) {
        setModal(false);
        form.resetFields();
      }
    } finally { setSaving(false); }
  };

  const submit = (values: CourseForm) => {
    if (!catalog?.complete || pending) return;
    const key = crypto.randomUUID();
    const shared = {
      ma_mon: values.ma_mon.trim().toUpperCase(), ten_khoa_hoc: values.ten_khoa_hoc.trim(),
      trinh_do: values.trinh_do.trim(), so_buoi: values.so_buoi, hoc_phi_chuan: values.hoc_phi_chuan,
    };
    const operation: PendingWrite = editing
      ? { kind: "update", key, slug: editing.slug, body: shared }
      : { kind: "create", key, body: { ...shared, ma_khoa_hoc: values.ma_khoa_hoc!.trim().toUpperCase(), slug: values.slug?.trim() || undefined } };
    void runWrite(operation);
  };

  const create = () => { setEditing(null); form.resetFields(); setModal(true); };
  const edit = (course: PublicCourse) => {
    setEditing(course);
    form.setFieldsValue({ ma_mon: course.subject_id, ten_khoa_hoc: course.name, trinh_do: course.level, so_buoi: course.session_count, hoc_phi_chuan: course.standard_fee });
    setModal(true);
  };

  const columns = [
    { title: "Khóa học", dataIndex: "name", render: (name: string, row: PublicCourse) => <><strong>{name}</strong><br /><span>{row.course_id} · {row.slug}</span></> },
    { title: "Môn học", dataIndex: "subject_name", render: (name: string, row: PublicCourse) => <>{name}<br /><span>{row.subject_id}</span></> },
    { title: "Trình độ", dataIndex: "level" },
    { title: "Thời lượng", dataIndex: "session_count", render: (value: number) => `${value} buổi` },
    { title: "Học phí chuẩn", dataIndex: "standard_fee", render: (value: number) => `${money.format(value)} ₫` },
    { title: "Cơ sở đang mở lớp", render: (_: unknown, row: PublicCourse) => row.branches.length ? <Space wrap size="small">{row.branches.map((branch) => <Tag key={branch.site_code}>{branch.site_code} · {branch.open_class_count} lớp</Tag>)}</Space> : "Chưa có lớp mở" },
    { title: "Thao tác", render: (_: unknown, row: PublicCourse) => <Space size="small"><Button size="small" disabled={!catalog?.complete || Boolean(pending)} onClick={() => edit(row)}>Sửa</Button><Popconfirm title="Xóa khóa học?" description="Chỉ xóa được khi chưa có lớp sử dụng; yêu cầu được đồng bộ tới mọi site." okText="Xóa" cancelText="Hủy" okButtonProps={{ danger: true, loading: saving }} onConfirm={() => void runWrite({ kind: "delete", slug: row.slug, key: crypto.randomUUID() })}><Button danger size="small" disabled={!catalog?.complete || Boolean(pending)}>Xóa</Button></Popconfirm></Space> },
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon title={error} />}
    {catalog && <>
      {!catalog.complete && <Alert type="warning" showIcon title="Danh mục chưa đồng nhất giữa các cơ sở. Tạm khóa thao tác ghi để tránh làm lệch bản sao." description={`Site thiếu: ${catalog.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${catalog.inconsistent_sites.join(", ") || "không có"}.`} />}
      {pending && <Alert type="warning" showIcon title="Yêu cầu đồng bộ chưa hoàn tất" description={<Space orientation="vertical"><span>Giữ nguyên nội dung và mã yêu cầu để tránh tạo thao tác trùng. Site chưa xác nhận: {pending.missingSites.join(", ") || "chưa xác định; API chưa xác nhận kết quả"}.</span><Button size="small" loading={saving} onClick={() => void runWrite(pending.operation)}>Thử lại đúng yêu cầu</Button></Space>} />}
    </>}
    <Card title={`Quản lý khóa học${catalog ? ` · ${catalog.count}` : ""}`} extra={<Button type="primary" onClick={create} disabled={!catalog?.complete || Boolean(pending)}>Tạo khóa học</Button>}>
      <Table rowKey="course_id" loading={loading} columns={columns} dataSource={catalog?.results || []} scroll={{ x: 1050 }} locale={{ emptyText: <Empty description={error ? "Không tải được dữ liệu từ các cơ sở" : "Chưa có khóa học"} /> }} />
    </Card>
    <Modal title={editing ? `Sửa khóa học · ${editing.course_id}` : "Tạo khóa học dùng chung"} open={modal} onCancel={() => setModal(false)} footer={null} destroyOnHidden>
      <Form form={form} layout="vertical" onFinish={submit}>
        {!editing && <>
          <Form.Item name="ma_khoa_hoc" label="Mã khóa học" rules={[{ required: true }, { pattern: /^KH-[A-Z0-9]+(?:-[A-Z0-9]+)*$/, message: "Dùng định dạng KH-TOEIC-700." }]}><Input maxLength={30} placeholder="KH-TOEIC-700" /></Form.Item>
          <Form.Item name="slug" label="Slug (để trống sẽ tự tạo)"><Input maxLength={160} placeholder="luyen-thi-toeic-700" /></Form.Item>
        </>}
        <Alert type="info" showIcon title="Mã môn phải là môn học đã tồn tại và có cùng dữ liệu trên tất cả site đang hoạt động." style={{ marginBottom: 16 }} />
        <Form.Item name="ma_mon" label="Mã môn học" rules={[{ required: true, max: 30 }]}><Input maxLength={30} /></Form.Item>
        <Form.Item name="ten_khoa_hoc" label="Tên khóa học" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
        <Form.Item name="trinh_do" label="Trình độ" rules={[{ required: true, max: 30 }]}><Input maxLength={30} placeholder="IELTS 6.5" /></Form.Item>
        <Form.Item name="so_buoi" label="Số buổi học" rules={[{ required: true }]}><InputNumber min={1} max={32767} precision={0} style={{ width: "100%" }} /></Form.Item>
        <Form.Item name="hoc_phi_chuan" label="Học phí chuẩn (đồng)" rules={[{ required: true }]}><InputNumber min={0} max={999999999999999999} precision={0} style={{ width: "100%" }} /></Form.Item>
        <Button type="primary" htmlType="submit" block loading={saving}>{editing ? "Lưu và đồng bộ" : "Tạo và đồng bộ"}</Button>
      </Form>
    </Modal>
  </Space>;
}
