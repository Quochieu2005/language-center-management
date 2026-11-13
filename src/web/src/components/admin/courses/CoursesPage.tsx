"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, App, Button, Card, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tag } from "antd";
import { catalogApi, type PublicCourse, type PublicCourseList, type SharedCourseCreateInput, type SharedCoursePatchInput, type SharedSubjectList } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import styles from "./CoursesPage.module.scss";

type CourseForm = {
  ma_khoa_hoc?: string;
  ma_mon: string;
  ten_khoa_hoc: string;
  trinh_do: string;
  so_buoi?: number | null;
  thoi_luong_so?: number;
  thoi_luong_don_vi?: "thang" | "ngay";
  hoc_phi_chuan: number;
};
type PendingWrite =
  | { kind: "create"; key: string; body: SharedCourseCreateInput }
  | { kind: "update"; key: string; slug: string; body: SharedCoursePatchInput }
  | { kind: "delete"; key: string; slug: string };
type PendingSync = { operation: PendingWrite; missingSites: string[] };

const money = new Intl.NumberFormat("vi-VN");
const durationNumber = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const previewSlug = (name: string) => name
  .replace(/[đĐ]/g, (letter) => letter === "đ" ? "d" : "D")
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .replace(/[^\w\s-]/g, "")
  .replace(/[-\s]+/g, "-")
  .slice(0, 160)
  .replace(/^[-_]+|[-_]+$/g, "");

export default function CoursesPage() {
  const { message, modal: confirmModal } = App.useApp();
  const [catalog, setCatalog] = useState<PublicCourseList | null>(null);
  const [subjects, setSubjects] = useState<SharedSubjectList | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(false);
  const [subjectPickerOpen, setSubjectPickerOpen] = useState(false);
  const [editing, setEditing] = useState<PublicCourse | null>(null);
  const [pending, setPending] = useState<PendingSync | null>(null);
  const [form] = Form.useForm<CourseForm>();
  const formScrollRef = useRef<HTMLDivElement>(null);
  const courseName = Form.useWatch("ten_khoa_hoc", form) || "";
  const durationUnit = Form.useWatch("thoi_luong_don_vi", form);
  const courseSlug = previewSlug(courseName);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setCatalog(null);
    setSubjects(null);
    try {
      const [courseResult, subjectResult] = await Promise.all([
        catalogApi.publicCourses(), catalogApi.sharedSubjects(),
      ]);
      setCatalog(courseResult);
      setSubjects(subjectResult);
    }
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
      const missingSites = reason instanceof ApiError && Array.isArray(reason.payload.missing_sites)
        ? reason.payload.missing_sites.filter((site): site is string => typeof site === "string")
        : [];
      if (!(reason instanceof ApiError) || reason.status >= 500) setPending({ operation, missingSites });
      else setPending(null);
      setError(reason instanceof Error ? reason.message : "Chưa xác nhận được kết quả. Hãy thử lại cùng yêu cầu.");
      if (!(reason instanceof ApiError) || reason.status >= 500) {
        setModal(false);
        form.resetFields();
      }
    } finally { setSaving(false); }
  };

  const submit = (values: CourseForm) => {
    if (!catalog?.complete || !subjects?.complete || pending) return;
    if (!editing && (values.thoi_luong_so == null || !values.thoi_luong_don_vi)) return;
    const key = crypto.randomUUID();
    const shared = {
      ma_khoa_hoc: values.ma_khoa_hoc!.trim().toUpperCase(),
      ma_mon: values.ma_mon.trim().toUpperCase(), ten_khoa_hoc: values.ten_khoa_hoc.trim(),
      trinh_do: values.trinh_do.trim(), so_buoi: values.so_buoi ?? null, hoc_phi_chuan: values.hoc_phi_chuan,
      ...(values.thoi_luong_so != null && values.thoi_luong_don_vi
        ? { thoi_luong_so: values.thoi_luong_so, thoi_luong_don_vi: values.thoi_luong_don_vi }
        : {}),
    };
    const operation: PendingWrite = editing
      ? { kind: "update", key, slug: editing.slug, body: shared }
      : { kind: "create", key, body: {
        ...shared,
        thoi_luong_so: values.thoi_luong_so!,
        thoi_luong_don_vi: values.thoi_luong_don_vi!,
      } };
    void runWrite(operation);
  };

  const create = () => { setEditing(null); setSubjectPickerOpen(false); form.resetFields(); setModal(true); };
  const edit = (course: PublicCourse) => {
    setEditing(course);
    setSubjectPickerOpen(false);
    form.setFieldsValue({ ma_khoa_hoc: course.course_id, ma_mon: course.subject_id, ten_khoa_hoc: course.name, trinh_do: course.level, so_buoi: course.session_count, thoi_luong_so: course.thoi_luong_so == null ? undefined : Number(course.thoi_luong_so), thoi_luong_don_vi: course.thoi_luong_don_vi ?? undefined, hoc_phi_chuan: course.standard_fee });
    setModal(true);
  };

  const canWrite = Boolean(catalog?.complete && subjects?.complete && !pending && !loading);

  const columns = [
    { title: "Khóa học", dataIndex: "name", render: (name: string, row: PublicCourse) => <><strong>{name}</strong><br /><span>{row.course_id} · {row.slug}</span></> },
    { title: "Môn học", dataIndex: "subject_name", render: (name: string, row: PublicCourse) => <>{name}<br /><span>{row.subject_id}</span></> },
    { title: "Trình độ", dataIndex: "level" },
    { title: "Số buổi học", dataIndex: "session_count", render: (value: number | null) => value == null ? "Chưa chốt" : `${value} buổi` },
    { title: "Thời gian hoàn thành", render: (_: unknown, row: PublicCourse) => row.thoi_luong_so && row.thoi_luong_don_vi ? `${durationNumber.format(Number(row.thoi_luong_so))} ${row.thoi_luong_don_vi === "thang" ? "tháng" : "ngày"}` : "Chưa cập nhật" },
    { title: "Học phí chuẩn", dataIndex: "standard_fee", render: (value: number) => `${money.format(value)} ₫` },
    { title: "Cơ sở đang mở lớp", render: (_: unknown, row: PublicCourse) => row.branches.length ? <Space wrap size="small">{row.branches.map((branch) => <Tag key={branch.site_code}>{branch.site_code} · {branch.open_class_count} lớp</Tag>)}</Space> : "Chưa có lớp mở" },
    { title: "Thao tác", render: (_: unknown, row: PublicCourse) => <Space size="small"><Button size="small" disabled={!canWrite} onClick={() => edit(row)}>Sửa</Button><Button danger size="small" disabled={!canWrite} onClick={() => confirmModal.confirm({ title: "Xóa khóa học?", content: "Chỉ xóa được khi chưa có lớp sử dụng; yêu cầu được đồng bộ tới mọi site.", okText: "Xóa", cancelText: "Hủy", okButtonProps: { danger: true, loading: saving }, onOk: () => runWrite({ kind: "delete", slug: row.slug, key: crypto.randomUUID() }) })}>Xóa</Button></Space> },
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon title={error} />}
    {catalog && <>
      {!catalog.complete && <Alert type="warning" showIcon title="Danh mục chưa đồng nhất giữa các cơ sở. Tạm khóa thao tác ghi để tránh làm lệch bản sao." description={`Site thiếu: ${catalog.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${catalog.inconsistent_sites.join(", ") || "không có"}.`} />}
      {subjects && !subjects.complete && <Alert type="warning" showIcon title="Danh sách môn học chưa đối chiếu đủ các cơ sở. Tạm khóa tạo/sửa khóa học." description={`Site thiếu: ${subjects.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${subjects.inconsistent_sites.join(", ") || "không có"}.`} />}
      {pending && <Alert type="warning" showIcon title="Yêu cầu đồng bộ chưa hoàn tất" description={<Space orientation="vertical"><span>Giữ nguyên nội dung và mã yêu cầu để tránh tạo thao tác trùng. Site chưa xác nhận: {pending.missingSites.join(", ") || "chưa xác định; API chưa xác nhận kết quả"}.</span><Button size="small" loading={saving} onClick={() => void runWrite(pending.operation)}>Thử lại đúng yêu cầu</Button></Space>} />}
    </>}
    <Card title={`Quản lý khóa học${catalog ? ` · ${catalog.count}` : ""}`} extra={<Button type="primary" onClick={create} disabled={!canWrite}>Tạo khóa học</Button>}>
      <Table rowKey="course_id" loading={loading} columns={columns} dataSource={catalog?.results || []} scroll={{ x: 1050 }} locale={{ emptyText: <Empty description={error ? "Không tải được dữ liệu từ các cơ sở" : "Chưa có khóa học"} /> }} />
    </Card>
    <Modal title={editing ? `Sửa khóa học · ${editing.course_id}` : "Tạo khóa học dùng chung"} open={modal} afterOpenChange={(open) => { if (open) formScrollRef.current?.scrollTo({ top: 0 }); }} onCancel={() => { setModal(false); setSubjectPickerOpen(false); }} footer={null} width="min(920px, calc(100vw - 32px))" styles={{ body: { padding: 0, overflow: "hidden" } }} destroyOnHidden>
      <div ref={formScrollRef} style={{ maxHeight: "calc(100vh - 160px)", overflowY: "auto", overflowX: "hidden", padding: 24 }}>
      <Form form={form} layout="vertical" onFinish={submit}>
        <div className={styles.formGrid}>
          <Form.Item
            name="ma_khoa_hoc"
            label="Mã khóa học"
            extra={editing ? "Có thể đổi mã khóa học; các lớp đang dùng mã này sẽ được cập nhật và đồng bộ tới các cơ sở." : undefined}
            style={{ gridColumn: "1 / -1" }}
            normalize={(value: string) => value?.trim().toUpperCase().replace(/[‐‑‒–—−]/g, "-")}
            validateTrigger={["onChange", "onBlur"]}
            rules={[
              { required: true, message: "Nhập mã khóa học." },
              {
                validator: (_, value: string | undefined) =>
                  !value || /^KH-[A-Z0-9]+(?:-[A-Z0-9]+)*$/.test(value.trim().toUpperCase())
                    ? Promise.resolve()
                    : Promise.reject(new Error("Mã phải bắt đầu bằng KH-. Ví dụ: KH-TOEIC-450-550.")),
              },
            ]}
          >
            <Input maxLength={30} placeholder="KH-TOEIC-450-550" />
          </Form.Item>
        </div>
        <Alert type="info" showIcon title="Mã môn phải là môn học đã tồn tại và có cùng dữ liệu trên tất cả site đang hoạt động." style={{ marginBottom: 16 }} />
        <div className={styles.formGrid}>
          <Form.Item label="Mã môn học" extra="Bấm Chọn mã môn để chọn môn có sẵn.">
            <Space.Compact style={{ width: "100%" }}>
              <Form.Item name="ma_mon" noStyle rules={[{ required: true, max: 30 }, { validator: (_, value: string | undefined) => !value || subjects?.results.some((subject) => subject.ma_mon.toUpperCase() === value.trim().toUpperCase()) ? Promise.resolve() : Promise.reject(new Error("Mã môn không tồn tại trong danh mục dùng chung.")) }]}>
                <Input readOnly placeholder="Chưa chọn mã môn" />
              </Form.Item>
              <Button htmlType="button" disabled={!subjects?.complete || !subjects.results.length} onClick={() => setSubjectPickerOpen(true)}>Chọn mã môn</Button>
            </Space.Compact>
          </Form.Item>
          <Form.Item name="ten_khoa_hoc" label="Tên khóa học" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
          <Form.Item label="Slug dự kiến" extra="Tự tạo theo tên khóa học; API sẽ từ chối nếu slug đã được dùng." style={{ gridColumn: "1 / -1" }}>
            <Input value={courseSlug} readOnly placeholder="Nhập tên khóa học để xem slug" />
          </Form.Item>
          <Form.Item name="trinh_do" label="Trình độ" rules={[{ required: true, max: 30 }]}><Input maxLength={30} placeholder="IELTS 6.5" /></Form.Item>
          <Form.Item name="so_buoi" label="Số buổi tham khảo (không bắt buộc)" extra="Có thể để trống. Khi xếp lớp, số buổi thực tế được tính theo ngày bắt đầu/kết thúc và các thứ đã chọn."><InputNumber min={1} max={32767} precision={0} style={{ width: "100%" }} placeholder="Để trống nếu chưa chốt" /></Form.Item>
          <Form.Item name="thoi_luong_so" label="Thời gian hoàn thành" extra="Tháng có thể nhập tối đa 2 số lẻ, ví dụ 3,5; ngày phải là số nguyên." dependencies={["thoi_luong_don_vi"]} rules={[{ required: !editing, message: "Nhập số tháng hoặc ngày." }, { validator: (_, value: number | undefined) => {
            const unit = form.getFieldValue("thoi_luong_don_vi");
            if (editing && value == null && !unit) return Promise.resolve();
            if (value == null || !unit) return Promise.reject(new Error("Nhập cả số lượng và đơn vị tháng/ngày."));
            if (unit === "ngay" && !Number.isInteger(value)) return Promise.reject(new Error("Thời lượng tính theo ngày phải là số nguyên."));
            if (unit === "thang" && Number(value.toFixed(2)) !== value) return Promise.reject(new Error("Thời lượng tháng chỉ được có tối đa 2 chữ số thập phân."));
            return Promise.resolve();
          } }]}><InputNumber min={0.01} max={99999.99} decimalSeparator="," step={durationUnit === "ngay" ? 1 : 0.5} style={{ width: "100%" }} placeholder="Ví dụ: 3,5" /></Form.Item>
          <Form.Item name="thoi_luong_don_vi" label="Đơn vị thời gian" dependencies={["thoi_luong_so"]} rules={[{ required: !editing, message: "Chọn tháng hoặc ngày." }, { validator: (_, value: string | undefined) => {
            const amount = form.getFieldValue("thoi_luong_so");
            if (editing && !value && amount == null) return Promise.resolve();
            return value && amount != null ? Promise.resolve() : Promise.reject(new Error("Chọn đơn vị tương ứng với số lượng."));
          } }]}><Select options={[{ value: "thang", label: "Tháng" }, { value: "ngay", label: "Ngày" }]} placeholder="Chọn đơn vị" /></Form.Item>
          <Form.Item name="hoc_phi_chuan" label="Học phí chuẩn (đồng)" rules={[{ required: true }]}><InputNumber<number> min={0} max={999999999999999999} precision={0} formatter={(value) => value == null ? "" : money.format(value)} parser={(value) => Number(value?.replace(/\D/g, "") || 0)} style={{ width: "100%" }} /></Form.Item>
        </div>
        <Button type="primary" htmlType="submit" block loading={saving}>{editing ? "Lưu và đồng bộ" : "Tạo và đồng bộ"}</Button>
      </Form>
      </div>
    </Modal>
    <Modal title="Chọn môn học" open={subjectPickerOpen} onCancel={() => setSubjectPickerOpen(false)} footer={null} width="min(480px, calc(100vw - 32px))" destroyOnHidden>
      {subjects?.results.length ? <Space orientation="vertical" size="small" style={{ width: "100%" }}>
        {subjects.results.map((subject) => <Button key={subject.ma_mon} block style={{ height: "auto", padding: "12px 16px", textAlign: "left" }} onClick={() => { form.setFieldValue("ma_mon", subject.ma_mon); setSubjectPickerOpen(false); }}>
          <Space><Tag>{subject.ma_mon}</Tag><span>{subject.ten_mon}</span></Space>
        </Button>)}
      </Space> : <Empty description="Chưa có môn học dùng chung để chọn." />}
    </Modal>
  </Space>;
}
