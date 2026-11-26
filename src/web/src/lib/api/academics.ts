import { apiRequest, jsonBody, query } from "./client";

export type ApiRow = Record<string, unknown>;
export type ApiList<T = ApiRow> = {
  count: number | null; limit: number; offset: number; site_code?: string; results: T[];
  scope?: "LOCAL" | "GLOBAL"; complete?: boolean; missing_sites?: string[]; site_codes?: string[];
};
export type ClassRow = {
  class_id: string; site_code: string; course_id: string; course_name: string; teacher_id: string;
  teacher_name: string; room_id: string; room_name: string; name: string; capacity: number;
  current_count: number; registered_count: number; remaining_seats: number; capacity_consistent: boolean;
  start_date: string; end_date: string | null; schedule: string; start_time: string; end_time: string; status: string;
};
export type ClassCourseOption = {
  course_id: string; name: string; subject_name: string; level: string;
  session_count: number | null; duration_value: number | string | null;
  duration_unit: "thang" | "ngay" | null; standard_fee: number;
};
export type ClassCourseOptionList = { site_code: string; count: number; results: ClassCourseOption[] };
export type RoomRow = { room_id: string; site_code: string; name: string; capacity: number; status: string; class_count: number; student_count: number };
export type RoomRosterStudent = { student_id: string; student_slug: string; student_name: string; total_due: number; amount_paid: number; balance: number; tuition_status: "chua_co_khoan_phi" | "chua_dong" | "dong_mot_phan" | "da_dong" };
export type RoomRosterClass = { class_id: string; class_name: string; status: string; student_count: number; students: RoomRosterStudent[] };
export type RoomRoster = { room_id: string; site_code: string; room_name: string; class_count: number; student_count: number; classes: RoomRosterClass[] };
export type EnrollmentRow = { enrollment_id: string; student_id: string; student_slug: string; full_name: string; enrollment_status: string; student_status: string };
export type TeacherScheduleRow = { session_id: string; class_id: string; class_name: string; course_name: string; session_number: number; date: string; start_time: string; end_time: string; room_id: string; room_name: string | null; status: string; note: string | null; can_edit_attendance: boolean };
export type SessionRow = { session_id: string; session_number: number; date: string; start_time: string; end_time: string; room_id: string; room_name: string; teacher_id: string; teacher_name: string; status: string; note: string | null };
export type TuitionRow = { tuition_id: string; site_code: string; enrollment_id: string; student_id: string; student_slug: string; student_name: string; student_email: string | null; class_id: string; class_name: string; course_name: string; amount_due: number; discount: number; total_due: number; amount_paid: number; balance: number; status: string; due_date: string | null };
export type TuitionReceipt = { receipt_id: string; type: "thu" | "hoan"; amount: number; payment_method: "tien_mat" | "chuyen_khoan" | "the"; paid_at: string; original_receipt_id: string | null; note: string | null; refunded_amount: number; refundable_amount: number };
export type TransferRow = { transfer_id: string; source_site: string; target_site: string; student_slug: string; student_id: string; student_name: string; status: string; reason: string; requested_at: string; decision_reason?: string | null; tuition_count: number; tuition_total_due: number; tuition_amount_paid: number; tuition_balance: number; tuition_status: "chua_co_khoan_phi" | "chua_dong" | "dong_mot_phan" | "da_dong" };
export type SePayPaymentOption = "next_installment" | "half" | "full";
export type SePayCheckout = { action: string; method: string; fields: Record<string, string> };
export type StudentSePayPayment = { site_code: string; attempt_id: string; tuition_id: string; installment_id: string; amount: number; payment_code: string; status: "cho_thanh_toan" | "da_thanh_toan" | "het_han" | "can_doi_soat" | "da_huy"; expires_at: string; checkout: SePayCheckout | null; option?: SePayPaymentOption };

export const academicsApi = {
  health: () => apiRequest<{ status: string; service?: string }>("/health/"),
  classes: (site_code?: string, options: { search?: string; status?: string; limit?: number; offset?: number } = {}) => apiRequest<ApiList<ClassRow>>(`/admin/classes/${query({ site_code, ...options })}`),
  classCourseOptions: (site_code?: string) => apiRequest<ClassCourseOptionList>(`/admin/classes/course-options/${query({ site_code })}`),
  createClass: (body: { site_code?: string; course_id: string; teacher_id: string; room_id: string; name: string; capacity: number; start_date: string; end_date: string; weekdays: number[]; start_time: string; end_time: string }) => apiRequest<ClassRow & { session_count: number }>("/admin/classes/", { method: "POST", body: jsonBody(body) }),
  classDetail: (id: string, site_code: string) => apiRequest<ClassRow & { session_count: number }>(`/admin/classes/${encodeURIComponent(id)}/${query({ site_code })}`),
  updateClass: (id: string, site_code: string, body: { name?: string; capacity?: number }) => apiRequest<ClassRow>(`/admin/classes/${encodeURIComponent(id)}/${query({ site_code })}`, { method: "PATCH", body: jsonBody(body) }),
  deleteClass: (id: string, site_code: string) => apiRequest<{ class_id: string; site_code: string; cancelled: boolean }>(`/admin/classes/${encodeURIComponent(id)}/${query({ site_code })}`, { method: "DELETE" }),
  roster: (id: string, site_code: string, offset = 0) => apiRequest<ApiList<EnrollmentRow>>(`/admin/classes/${encodeURIComponent(id)}/students/${query({ site_code, limit: 100, offset })}`),
  classSessions: (id: string, site_code: string) => apiRequest<ApiList<SessionRow>>(`/admin/classes/${encodeURIComponent(id)}/sessions/${query({ site_code, limit: 100 })}`),
  assignTeacher: (id: string, site_code: string, teacher_id: string) => apiRequest<ClassRow>(`/admin/classes/${encodeURIComponent(id)}/teacher/${query({ site_code })}`, { method: "PUT", body: jsonBody({ teacher_id }) }),
  rooms: (site_code?: string, options: { search?: string; status?: string; limit?: number; offset?: number } = {}) => apiRequest<ApiList<RoomRow>>(`/admin/rooms/${query({ site_code, limit: 100, ...options })}`),
  roomRoster: (id: string, site_code: string) => apiRequest<RoomRoster>(`/admin/rooms/${encodeURIComponent(id)}/${query({ site_code })}`),
  createRoom: (body: { site_code?: string; name: string; capacity: number }) => apiRequest<RoomRow>("/admin/rooms/", { method: "POST", body: jsonBody(body) }),
  updateRoom: (id: string, site_code: string, body: { name: string; capacity: number; status: string }) => apiRequest<RoomRow>(`/admin/rooms/${encodeURIComponent(id)}/${query({ site_code })}`, { method: "PATCH", body: jsonBody(body) }),
  deleteRoom: (id: string, site_code: string) => apiRequest<{ room_id: string; site_code: string; deleted: boolean }>(`/admin/rooms/${encodeURIComponent(id)}/${query({ site_code })}`, { method: "DELETE" }),
  enroll: (body: { site_code?: string; student_id: string; class_id: string }) => apiRequest<ApiRow>("/admin/enrollments/", { method: "POST", body: jsonBody(body) }),
  moveEnrollment: (id: string, site_code: string, target_class_id: string) => apiRequest<ApiRow>(`/admin/enrollments/${encodeURIComponent(id)}/class/${query({ site_code })}`, { method: "POST", body: jsonBody({ target_class_id }) }),
  tuition: (site_code?: string, options: { status?: "con_no" | "chua_dong" | "dong_mot_phan" | "da_dong" | "hoan_tien"; student_slug?: string; search?: string; limit?: number; offset?: number } = {}) => apiRequest<ApiList<TuitionRow>>(`/admin/tuition/${query({ site_code, limit: 20, ...options })}`),
  installments: (id: string, site_code: string) => apiRequest<ApiRow>(`/admin/tuition/${encodeURIComponent(id)}/installments/${query({ site_code })}`),
  saveInstallments: (id: string, site_code: string, body: { payment_mode: "full" | "monthly"; installment_count?: 3 | 6 | 9 | 12; first_due_date: string }) => apiRequest<ApiRow>(`/admin/tuition/${encodeURIComponent(id)}/installments/${query({ site_code })}`, { method: "PUT", body: jsonBody(body) }),
  collectTuition: (id: string, site_code: string, body: { idempotency_key: string; amount: number; payment_method: "tien_mat" | "chuyen_khoan" | "the"; note?: string }) => apiRequest<ApiRow>(`/admin/tuition/${encodeURIComponent(id)}/receipts/${query({ site_code })}`, { method: "POST", body: jsonBody(body) }),
  tuitionReceipts: (id: string, site_code: string) => apiRequest<{ site_code: string; tuition_id: string; count: number; results: TuitionReceipt[] }>(`/admin/tuition/${encodeURIComponent(id)}/receipts/${query({ site_code })}`),
  refundTuition: (id: string, receiptId: string, site_code: string, body: { idempotency_key: string; amount: number; payment_method: "tien_mat" | "chuyen_khoan" | "the"; reason: string }) => apiRequest<ApiRow>(`/admin/tuition/${encodeURIComponent(id)}/receipts/${encodeURIComponent(receiptId)}/refund/${query({ site_code })}`, { method: "POST", body: jsonBody(body) }),
  invoice: (tuitionId: string, receiptId: string, site_code: string) => apiRequest<ApiRow>(`/admin/tuition/${encodeURIComponent(tuitionId)}/receipts/${encodeURIComponent(receiptId)}/invoice/${query({ site_code })}`),
  sendTuitionReminders: (classId: string, site_code: string, threshold?: number) => apiRequest<ApiRow>(`/admin/classes/${encodeURIComponent(classId)}/tuition-reminders/${query({ site_code })}`, { method: "POST", body: jsonBody(threshold === undefined ? {} : { threshold }) }),
  transfers: (options: { site_code?: string; status?: string } = {}) => apiRequest<{ complete: boolean; missing_sites: string[]; site_codes: string[]; count: number; results: TransferRow[] }>(`/admin/transfers/${query({ limit: 100, ...options })}`),
  requestTransfer: (body: { student_slug: string; target_site: string; reason: string }) => apiRequest<ApiRow>("/admin/transfers/", { method: "POST", body: jsonBody(body) }),
  decideTransfer: (source: string, id: string, body: { decision: "approve" | "reject"; reason?: string }) => apiRequest<ApiRow>(`/admin/transfers/${encodeURIComponent(source)}/${encodeURIComponent(id)}/decision/`, { method: "POST", body: jsonBody(body) }),
  retryTransfer: (source: string, id: string) => apiRequest<ApiRow>(`/admin/transfers/${encodeURIComponent(source)}/${encodeURIComponent(id)}/retry/`, { method: "POST", body: "{}" }),
  teacherClasses: () => apiRequest<ApiList<ApiRow>>("/teacher/classes/"),
  teacherSchedule: () => apiRequest<ApiList<TeacherScheduleRow>>("/teacher/schedule/"),
  teacherSessions: (id: string) => apiRequest<ApiList<SessionRow>>(`/teacher/classes/${encodeURIComponent(id)}/sessions/`),
  attendance: (id: string) => apiRequest<ApiRow>(`/teacher/sessions/${encodeURIComponent(id)}/attendance/`),
  saveAttendance: (id: string, items: { enrollment_id: string; status: "co_mat" | "tre" | "vang_co_phep" | "vang_khong_phep"; note?: string }[]) => apiRequest<ApiRow>(`/teacher/sessions/${encodeURIComponent(id)}/attendance/`, { method: "PUT", body: jsonBody({ items }) }),
  grades: (id: string) => apiRequest<ApiRow>(`/teacher/enrollments/${encodeURIComponent(id)}/grades/`),
  gradeHistory: (id: string) => apiRequest<ApiRow>(`/teacher/enrollments/${encodeURIComponent(id)}/grades/history/`),
  saveGrade: (id: string, gradeType: string, score: number) => apiRequest<ApiRow>(`/teacher/enrollments/${encodeURIComponent(id)}/grades/${encodeURIComponent(gradeType)}/`, { method: "PUT", body: jsonBody({ score }) }),
  studentEnrollments: (slug: string) => apiRequest<ApiList<ApiRow>>(`/students/profile/${encodeURIComponent(slug)}/enrollments/`),
  studentSchedule: (slug: string) => apiRequest<ApiList<ApiRow>>(`/students/profile/${encodeURIComponent(slug)}/schedule/`),
  studentTuition: (slug: string) => apiRequest<ApiList<ApiRow>>(`/students/profile/${encodeURIComponent(slug)}/tuition/`),
  createStudentSePayPayment: (slug: string, tuitionId: string, body: { option: SePayPaymentOption }, idempotencyKey: string) => apiRequest<StudentSePayPayment>(`/students/profile/${encodeURIComponent(slug)}/tuition/${encodeURIComponent(tuitionId)}/payments/sepay/`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: jsonBody(body) }),
  studentPaymentStatus: (slug: string, attemptId: string) => apiRequest<StudentSePayPayment>(`/students/profile/${encodeURIComponent(slug)}/payments/${encodeURIComponent(attemptId)}/`),
  studentGrades: (slug: string) => apiRequest<ApiList<ApiRow>>(`/students/profile/${encodeURIComponent(slug)}/grades/`),
  studentProfile: (slug: string) => apiRequest<ApiRow>(`/students/profile/${encodeURIComponent(slug)}/`),
  updateStudentProfile: (slug: string, body: ApiRow) => apiRequest<ApiRow>(`/students/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
};
