"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, App, Button, Card, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tag } from "antd";
import { catalogApi, type CourseClassSession, type CourseClassSessionSummary, type PublicCourse, type PublicCourseList, type SharedCourseCreateInput, type SharedCoursePatchInput, type SharedCourseSyncStatus, type SharedSubjectList } from "@/lib/api/catalog";
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
type PendingSync = { operation: PendingWrite; missingSites: string[]; durable: boolean };

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
  const [classSessions, setClassSessions] = useState<CourseClassSessionSummary | null>(null);
  const [classSessionsError, setClassSessionsError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(false);
  const [subjectPickerOpen, setSubjectPickerOpen] = useState(false);
  const [editing, setEditing] = useState<PublicCourse | null>(null);
  const [pending, setPending] = useState<PendingSync | null>(null);
  const [syncStatus, setSyncStatus] = useState<SharedCourseSyncStatus | null>(null);
  const [syncError, setSyncError] = useState("");
  const [form] = Form.useForm<CourseForm>();
  const formScrollRef = useRef<HTMLDivElement>(null);
  const courseName = Form.useWatch("ten_khoa_hoc", form) || "";
  const durationUnit = Form.useWatch("thoi_luong_don_vi", form);
  const courseSlug = previewSlug(courseName);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setSyncError("");
    setCatalog(null);
    setSubjects(null);
    setClassSessions(null);
    setClassSessionsError("");
    const queueStatusRequest = catalogApi.reconcileCourseWrites().then((status) => {
      setSyncStatus(status);
      return status;
    }).catch((reason) => {
      setSyncError(reason instanceof Error ? reason.message : "Không kiểm tra được hàng đợi đồng bộ khóa học.");
      setSyncStatus(null);
      return null;
    });
    try {
      const [, [courseResult, subjectResult, sessionResult]] = await Promise.all([
        queueStatusRequest,
        Promise.all([
          catalogApi.publicCourses(),
          catalogApi.sharedSubjects(),
          catalogApi.courseClassSessions().catch((reason) => {
            setClassSessionsError(reason instanceof Error ? reason.message : "Không tải được số buổi theo lớp.");
            return null;
          }),
        ]),
      ]);
      setCatalog(courseResult);
      setSubjects(subjectResult);
      setClassSessions(sessionResult);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được danh mục khóa học."); }
    finally { setLoading(false); }
    return queueStatusRequest;
  }, []);
  useEffect(() => { queueMicrotask(() => { void load(); }); }, [load]);

  useEffect(() => {
    if (!syncStatus?.pending_count) return;
    let stopped = false;
    let running = false;
    const timer = window.setInterval(async () => {
      if (running) return;
      running = true;
      try {
        const next = await catalogApi.reconcileCourseWrites();
        if (stopped) return;
        setSyncStatus(next);
        setSyncError("");
        if (!next.pending_count) {
          setPending((current) => current?.durable ? null : current);
          await load();
        }
      } catch (reason) {
        if (!stopped) setSyncError(reason instanceof Error ? reason.message : "Chưa đối soát được hàng đợi đồng bộ.");
      } finally { running = false; }
    }, 10000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [load, syncStatus?.pending_count]);

  const retryQueueOperation = async (operationId: string) => {
    setSaving(true);
    try {
      const next = await catalogApi.reconcileCourseWrites(operationId);
      setSyncStatus(next);
      setSyncError("");
      if (!next.pending_count) {
        setPending(null);
        await load();
      }
    } catch (reason) {
      setSyncError(reason instanceof Error ? reason.message : "Chưa đối soát lại được yêu cầu.");
    } finally { setSaving(false); }
  };

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
        setPending({ operation, missingSites: result.missing_sites, durable: true });
        setModal(false);
        form.resetFields();
        message.warning("Yêu cầu đã được lưu. Site còn thiếu sẽ được đồng bộ tự động khi kết nối lại.");
        const refreshed = await load();
        if (refreshed?.pending_count === 0) setPending(null);
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
      if (!(reason instanceof ApiError) || reason.status >= 500) setPending({ operation, missingSites, durable: false });
      else setPending(null);
      setError(reason instanceof Error ? reason.message : "Chưa xác nhận được kết quả. Hãy thử lại cùng yêu cầu.");
      if (!(reason instanceof ApiError) || reason.status >= 500) {
        setModal(false);
        form.resetFields();
      }
    } finally { setSaving(false); }
  };

  const submit = (values: CourseForm) => {
    if (!canWrite) return;
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

  const catalogConsistent = Boolean(catalog && !catalog.inconsistent_sites.length && (catalog.complete || catalog.missing_sites.length));
  const subjectsConsistent = Boolean(subjects && !subjects.inconsistent_sites.length && (subjects.complete || subjects.missing_sites.length));
  const needsManualReview = Boolean(syncStatus?.operations.some((operation) => operation.status === "can_doi_soat"));
  const canWrite = Boolean(catalogConsistent && subjectsConsistent && !needsManualReview && (!pending || pending.durable) && !loading);
  const sessionsByCourse = new Map<string, CourseClassSession[]>();
  for (const item of classSessions?.results || []) {
    const sessions = sessionsByCourse.get(item.course_id) || [];
    sessions.push(item);
    sessionsByCourse.set(item.course_id, sessions);
  }

  const columns = [
    { title: "Khóa học", dataIndex: "name", render: (name: string, row: PublicCourse) => <><strong>{name}</strong><br /><span>{row.course_id} · {row.slug}</span></> },
    { title: "Môn học", dataIndex: "subject_name", render: (name: string, row: PublicCourse) => <>{name}<br /><span>{row.subject_id}</span></> },
    { title: "Trình độ", dataIndex: "level" },
    { title: "Số buổi chuẩn", dataIndex: "session_count", render: (value: number | null) => value == null ? "Chưa chốt" : `${value} buổi` },
    { title: "Số buổi đã xếp theo lớp", render: (_: unknown, row: PublicCourse) => {
      const classes = sessionsByCourse.get(row.course_id) || [];
      return classes.length ? <Space orientation="vertical" size="small">{classes.map((item) => <span key={`${item.site_code}-${item.class_id}`}>{item.site_code} · {item.class_name} ({item.class_id}) · {item.session_count} buổi</span>)}</Space> : "Chưa có lớp";
    } },
    { title: "Thời gian hoàn thành", render: (_: unknown, row: PublicCourse) => row.thoi_luong_so && row.thoi_luong_don_vi ? `${durationNumber.format(Number(row.thoi_luong_so))} ${row.thoi_luong_don_vi === "thang" ? "tháng" : "ngày"}` : "Chưa cập nhật" },
    { title: "Học phí chuẩn", dataIndex: "standard_fee", render: (value: number) => `${money.format(value)} ₫` },
    { title: "Cơ sở đang mở lớp", render: (_: unknown, row: PublicCourse) => row.branches.length ? <Space wrap size="small">{row.branches.map((branch) => <Tag key={branch.site_code}>{branch.site_code} · {branch.open_class_count} lớp</Tag>)}</Space> : "Chưa có lớp mở" },
    { title: "Thao tác", render: (_: unknown, row: PublicCourse) => <Space size="small"><Button size="small" disabled={!canWrite} onClick={() => edit(row)}>Sửa</Button><Button danger size="small" disabled={!canWrite} onClick={() => confirmModal.confirm({ title: "Xóa khóa học?", content: "Chỉ xóa được khi chưa có lớp sử dụng; yêu cầu được đồng bộ tới mọi site.", okText: "Xóa", cancelText: "Hủy", okButtonProps: { danger: true, loading: saving }, onOk: () => runWrite({ kind: "delete", slug: row.slug, key: crypto.randomUUID() }) })}>Xóa</Button></Space> },
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon title={error} />}
    {classSessionsError && <Alert type="warning" showIcon title="Không tải được số buổi theo lớp" description={classSessionsError} />}
    {classSessions && !classSessions.complete && <Alert type="warning" showIcon title="Số buổi lớp mới tải được một phần" description={`Thiếu site: ${classSessions.missing_sites.join(", ") || "không xác định"}.`} />}
    {syncError && <Alert type="warning" showIcon title="Chưa cập nhật được trạng thái hàng đợi" description={<Space orientation="vertical"><span>{syncError}</span><span>Mỗi lần ghi vẫn được API kiểm tra riêng. Nếu site điều phối không sẵn sàng hoặc danh mục đang lệch, API sẽ từ chối và giữ nguyên dữ liệu bạn nhập.</span><Button size="small" onClick={() => void load()}>Tải lại trạng thái</Button></Space>} />}
    {catalog && !catalog.complete && <Alert type={catalog.inconsistent_sites.length ? "error" : "warning"} showIcon title={catalog.inconsistent_sites.length ? "Danh mục khóa học đang lệch giữa các site; cần đối soát trước khi ghi." : "Danh sách khóa học thiếu site đang mất kết nối."} description={`Site thiếu: ${catalog.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${catalog.inconsistent_sites.join(", ") || "không có"}.${catalogConsistent ? " Có thể tạo/sửa; hệ thống sẽ lưu yêu cầu và chờ site thiếu đồng bộ." : ""}`} />}
    {subjects && !subjects.complete && <Alert type={subjects.inconsistent_sites.length ? "error" : "warning"} showIcon title={subjects.inconsistent_sites.length ? "Danh sách môn học đang lệch; chưa thể tạo/sửa khóa học." : "Danh sách môn học thiếu site đang mất kết nối."} description={`Site thiếu: ${subjects.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${subjects.inconsistent_sites.join(", ") || "không có"}.${subjectsConsistent ? " Các site đang kết nối nhất quán; yêu cầu khóa học sẽ chờ bản sao môn học còn thiếu nếu cần." : ""}`} />}
    {syncStatus && syncStatus.pending_count > 0 && <Alert type="warning" showIcon title="Đang chờ đồng bộ khóa học" description={<Space orientation="vertical"><span>Hàng đợi còn {syncStatus.pending_count} yêu cầu. Site chưa xác nhận: {syncStatus.pending_sites.join(", ") || "cần đối soát"}. Hệ thống tự thử mỗi 10 giây khi trang đang mở và khi bạn mở trang lần sau.</span>{syncStatus.operations.map((operation) => <Space key={operation.operation_id} wrap><span>{operation.action} · {operation.course_id || operation.slug} · {operation.status === "can_doi_soat" ? "cần đối soát" : `đang chờ ${operation.pending_sites.join(", ") || "site liên quan"}`}{operation.detail ? ` · ${operation.detail}` : ""}</span>{operation.status === "can_doi_soat" && <Button size="small" loading={saving} onClick={() => void retryQueueOperation(operation.operation_id)}>Đối soát lại</Button>}</Space>)}</Space>} />}
    {pending && (!pending.durable || syncError || !syncStatus) && <Alert type="warning" showIcon title="Chưa xác nhận được kết quả ghi" description={<Space orientation="vertical"><span>Giữ nguyên nội dung yêu cầu. Site chưa xác nhận: {pending.missingSites.join(", ") || "chưa xác định"}.</span><Button size="small" loading={saving} onClick={() => void runWrite(pending.operation)}>Thử lại đúng yêu cầu</Button></Space>} />}
    <Card title={`Quản lý khóa học${catalog ? ` · ${catalog.count}` : ""}`} extra={<Button type="primary" onClick={create} disabled={!canWrite}>Tạo khóa học</Button>}>
      <Table rowKey="course_id" loading={loading} columns={columns} dataSource={catalog?.results || []} scroll={{ x: 1400 }} locale={{ emptyText: <Empty description={error ? "Không tải được dữ liệu từ các cơ sở" : "Chưa có khóa học"} /> }} />
    </Card>
    <Modal title={editing ? `Sửa khóa học · ${editing.course_id}` : "Tạo khóa học dùng chung"} open={modal} afterOpenChange={(open) => { if (open) { formScrollRef.current?.scrollTo({ top: 0 }); if (editing) void form.validateFields(["ma_khoa_hoc"]).catch(() => undefined); } }} onCancel={() => { setModal(false); setSubjectPickerOpen(false); }} footer={null} width="min(920px, calc(100vw - 32px))" styles={{ body: { padding: 0, overflow: "hidden" } }} destroyOnHidden>
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
                  !value || /^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$/.test(value.trim().toUpperCase())
                    ? Promise.resolve()
                    : Promise.reject(new Error("Mã phải bắt đầu bằng chữ cái, chỉ dùng chữ/số và dấu gạch nối. Ví dụ: FG hoặc HK-TOEIC-450-550.")),
              },
            ]}
          >
            <Input maxLength={30} placeholder="FG hoặc HK-TOEIC-450-550" />
          </Form.Item>
        </div>
        <Alert type="info" showIcon title="Mã môn phải tồn tại và nhất quán trên các site đang kết nối. Site đang mất kết nối sẽ được kiểm tra khi đồng bộ." style={{ marginBottom: 16 }} />
        <div className={styles.formGrid}>
          <Form.Item label="Mã môn học" extra="Bấm Chọn mã môn để chọn môn có sẵn.">
            <Space.Compact style={{ width: "100%" }}>
              <Form.Item name="ma_mon" noStyle rules={[{ required: true, max: 30 }, { validator: (_, value: string | undefined) => !value || subjects?.results.some((subject) => subject.ma_mon.toUpperCase() === value.trim().toUpperCase()) ? Promise.resolve() : Promise.reject(new Error("Mã môn không tồn tại trong danh mục dùng chung.")) }]}>
                <Input readOnly placeholder="Chưa chọn mã môn" />
              </Form.Item>
              <Button htmlType="button" disabled={!subjectsConsistent || !subjects?.results.length} onClick={() => setSubjectPickerOpen(true)}>Chọn mã môn</Button>
            </Space.Compact>
          </Form.Item>
          <Form.Item name="ten_khoa_hoc" label="Tên khóa học" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
          <Form.Item label="Slug dự kiến" extra="Tự tạo theo tên khóa học; API sẽ từ chối nếu slug đã được dùng." style={{ gridColumn: "1 / -1" }}>
            <Input value={courseSlug} readOnly placeholder="Nhập tên khóa học để xem slug" />
          </Form.Item>
          <Form.Item name="trinh_do" label="Trình độ" rules={[{ required: true, max: 30 }]}><Input maxLength={30} placeholder="IELTS 6.5" /></Form.Item>
          <Form.Item name="so_buoi" label="Số buổi chuẩn theo chương trình (không bắt buộc)" extra="Đây là số buổi chuẩn của khóa; số buổi đã tạo được hiển thị riêng theo từng lớp."><InputNumber min={1} max={32767} precision={0} style={{ width: "100%" }} placeholder="Để trống nếu chưa chốt" /></Form.Item>
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
