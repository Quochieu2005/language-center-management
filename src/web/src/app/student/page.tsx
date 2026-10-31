"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Space, Tabs, Typography, message } from "antd";
import { academicsApi, type ApiRow } from "@/lib/api/academics";
import { RequireSession, useSession } from "@/lib/auth/session";
import { ApiDataTable } from "@/components/shared/ApiPage";

type PortalData = { profile: ApiRow | null; enrollments: ApiRow[]; schedule: ApiRow[]; tuition: ApiRow[]; grades: ApiRow[] };
export default function StudentRoute() { return <RequireSession roles={["hoc_vien"]}><StudentPortal /></RequireSession>; }

function StudentPortal() {
  const { user } = useSession();
  const [data, setData] = useState<PortalData>({ profile: null, enrollments: [], schedule: [], tuition: [], grades: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form] = Form.useForm();
  const load = useCallback(async () => {
    if (!user) return;
    const results = await Promise.allSettled([academicsApi.studentProfile(user.slug), academicsApi.studentEnrollments(user.slug), academicsApi.studentSchedule(user.slug), academicsApi.studentTuition(user.slug), academicsApi.studentGrades(user.slug)]);
    const failures = results.filter((item) => item.status === "rejected").map((item) => item.status === "rejected" && item.reason instanceof Error ? item.reason.message : "API lỗi");
    setError(failures.join(" · "));
    setData({ profile: results[0].status === "fulfilled" ? results[0].value : null, enrollments: results[1].status === "fulfilled" ? results[1].value.results : [], schedule: results[2].status === "fulfilled" ? results[2].value.results : [], tuition: results[3].status === "fulfilled" ? results[3].value.results : [], grades: results[4].status === "fulfilled" ? results[4].value.results : [] });
    if (results[0].status === "fulfilled") form.setFieldsValue(results[0].value);
    setLoading(false);
  }, [form, user]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const save = async (values: { phone?: string; address?: string }) => {
    if (!user) return;
    try { await academicsApi.updateStudentProfile(user.slug, values); message.success("Đã cập nhật thông tin liên hệ."); void load(); }
    catch (reason) { message.error(reason instanceof Error ? reason.message : "Không lưu được hồ sơ."); }
  };
  return <main style={{ maxWidth: 1200, margin: "24px auto", padding: 16 }}><Space direction="vertical" size="middle" style={{ width: "100%" }}><div><Typography.Title level={2}>Cổng học viên</Typography.Title><Typography.Text type="secondary">Dữ liệu cá nhân, đăng ký, lịch học, học phí và điểm của tài khoản hiện tại.</Typography.Text></div>
    {error && <Alert type="warning" showIcon title="Một số dữ liệu chưa tải được" description={error} />}
    <Card title="Hồ sơ của tôi"><Form form={form} layout="inline" onFinish={save}><Form.Item label="Họ tên"><Input value={String(data.profile?.full_name || "")} disabled /></Form.Item><Form.Item label="Điện thoại" name="phone"><Input maxLength={20} /></Form.Item><Form.Item label="Địa chỉ" name="address"><Input maxLength={300} /></Form.Item><Button type="primary" htmlType="submit">Lưu liên hệ</Button></Form></Card>
    <Card><Tabs items={[{ key: "enrollments", label: `Khóa học (${data.enrollments.length})`, children: <ApiDataTable rows={data.enrollments} loading={loading} /> }, { key: "schedule", label: `Lịch học (${data.schedule.length})`, children: <ApiDataTable rows={data.schedule} loading={loading} /> }, { key: "tuition", label: `Học phí (${data.tuition.length})`, children: <ApiDataTable rows={data.tuition} loading={loading} /> }, { key: "grades", label: `Điểm (${data.grades.length})`, children: <ApiDataTable rows={data.grades} loading={loading} /> }]} /></Card>
  </Space></main>;
}
