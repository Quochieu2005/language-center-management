import { apiRequest, jsonBody, query } from "./client";
import type { AvatarUploadIntent } from "./auth";

export type PageResult<T> = {
  count: number | null; limit: number; offset: number; results: T[]; site_code?: string;
  scope?: "LOCAL" | "GLOBAL"; complete?: boolean; missing_sites?: string[]; site_codes?: string[];
};
export type SiteCounts = {
  scope: "LOCAL" | "GLOBAL";
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  total_active_students: number;
  results: { site_code: string; active_students: number; in_transit_students?: number }[];
};
export type TuitionFinancialReport = {
  scope: "LOCAL" | "GLOBAL";
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  totals: { tuition_accounts: number; accounts_with_balance: number; total_due: number; net_collected: number; outstanding: number; total_collected: number; total_refunded: number };
  results: { site_code: string; tuition_accounts: number; accounts_with_balance: number; total_due: number; net_collected: number; outstanding: number; total_collected: number; total_refunded: number }[];
};
export type AdminSmall = {
  admin_id: string; site_code: string; full_name: string; phone: string | null;
  account_id: string; slug: string; username: string; email: string;
  avatar_secure_url: string | null;
  account_status: "active" | "inactive"; profile_status: "dang_lam" | "nghi_viec";
  credential_email_status: "ready" | "processing" | "sent" | "failed" | "unknown" | "changed";
};
export type Teacher = {
  teacher_id: string; account_id: string | null; slug: string | null; site_code: string;
  account_status: "active" | "inactive" | null; full_name: string; phone: string | null;
  email: string | null; username: string | null; specialty: string; avatar_secure_url: string | null;
  credential_email_status: "ready" | "processing" | "sent" | "failed" | "unknown" | "changed";
  status: "dang_day" | "tam_nghi" | "nghi_viec";
};
export type Employee = {
  employee_id: string; account_id: string; slug: string; username: string; email: string;
  site_code: string; job_title: "le_tan" | "tu_van" | "ke_toan";
  full_name: string; phone: string | null; account_status: "active" | "inactive";
  employee_status: "dang_lam" | "nghi_viec"; avatar_secure_url: string | null;
  credential_email_status?: "ready" | "processing" | "sent" | "failed" | "unknown" | "changed";
};
export type AdminNotification = {
  slug: string;
  site_code: string;
  category: string;
  severity: string;
  title: string;
  message: string;
  target_path: string | null;
  created_at: string;
};
export type AdminNotificationList = {
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  count: number;
  limit: number;
  offset: number;
  results: AdminNotification[];
};
export type CreateAdminNotification = {
  category: string;
  severity: string;
  audience: "admin_all" | "admin_big" | "admin_small";
  title: string;
  message: string;
  target_path: string | null;
};
export type AdminNotificationCreateResult = {
  site_code: string;
  slug: string;
  created: boolean;
};
export type AdminNotificationCreateResponse = {
  complete: boolean;
  site_codes: string[];
  missing_sites: string[];
  results: AdminNotificationCreateResult[];
};
export type AdminAuditLog = {
  log_id: string;
  log_type: "login" | "password_reset" | "system" | "sync";
  occurred_at: string;
  site_code: string;
  account_id: string | null;
  action: string | null;
  affected_table: string | null;
  record_id: string | null;
  result: "thanh_cong" | "that_bai" | null;
  destination_site: string | null;
};
export type AdminAuditLogList = {
  scope: "LOCAL" | "GLOBAL";
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  count: number;
  limit: number;
  offset: number;
  results: AdminAuditLog[];
};
export type Student = {
  student_id: string; slug: string; site_code: string; full_name: string;
  phone: string | null; email: string | null; avatar_secure_url: string | null; status: string;
  account_issued: boolean; account_issue_eligible: boolean;
};
export type CourseRegistration = {
  enrollment_id: string; enrolled_at: string; enrollment_status: string; student_id: string; slug: string;
  site_code: string; full_name: string; email: string | null; phone: string | null; class_id: string;
  class_name: string; course_name: string; account_issued: boolean; account_issue_eligible: boolean;
  has_website_account: boolean | null;
};
export type StudentProfile = {
  student_id: string; slug: string; site_code: string; full_name: string;
  birth_date: string | null; gender: string | null; phone: string | null;
  email: string | null; address: string | null; enrolled_on: string; status: string;
  avatar_secure_url: string | null;
};
export type StudentProfileWrite = {
  full_name: string; birth_date?: string | null; gender?: string | null;
  phone?: string | null; email?: string | null; address?: string | null; slug?: string;
};
export type ApiPage<T> = PageResult<T> & { complete?: boolean; missing_sites?: string[]; site_codes?: string[] };
export type AdminAvatarUploadIntent = AvatarUploadIntent;
export type AccountReplication = { replication_complete: boolean; replication_pending_sites: string[] };

export const adminApi = {
  studentCounts: (site_code?: string) => apiRequest<SiteCounts>(`/admin/reports/students-by-site/${query({ site_code })}`),
  tuitionFinancialSummary: (site_code?: string) => apiRequest<TuitionFinancialReport>(`/admin/reports/tuition-by-site/${query({ site_code })}`),
  adminSmalls: (site_code?: string, limit = 100, offset = 0) =>
    apiRequest<PageResult<AdminSmall> & { complete: boolean; missing_sites: string[]; site_codes: string[] }>(
      `/admin/admin-smalls/${query({ site_code, limit, offset })}`,
    ),
  createAdminSmall: (body: { full_name: string; email: string; site_code: string; username?: string; slug?: string; avatar_requested?: boolean }) =>
    apiRequest<AccountReplication & { account_id: string; admin_id: string; username: string; email: string; site_code: string; slug: string; account_status: "active"; role: "admin_small"; must_change_password: boolean; credential_email_status: "ready" | "unknown"; avatar_setup_token: string | null }>("/admin/admin-smalls/", { method: "POST", body: jsonBody(body) }),
  sendAdminSmallCredentials: (accountId: string) =>
    apiRequest<{ detail: string; email: string; status: "sent" }>(`/admin/admin-smalls/${encodeURIComponent(accountId)}/credential-email/`, { method: "POST" }),
  adminSmallProfile: (slug: string) => apiRequest<Record<string, unknown>>(`/admin/admin-smalls/profile/${encodeURIComponent(slug)}/`),
  updateAdminSmallProfile: (slug: string, body: { full_name?: string; phone?: string | null }) =>
    apiRequest<Record<string, unknown>>(`/admin/admin-smalls/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  updateAdminSmallStatus: (slug: string, status: "active" | "inactive") =>
    apiRequest<Record<string, unknown>>(`/admin/admin-smalls/${encodeURIComponent(slug)}/status/`, { method: "PATCH", body: jsonBody({ status }) }),
  deleteAdminSmall: (accountId: string) =>
    apiRequest<{ account_id: string; site_code: string; role: "admin_small"; deleted: boolean; detail: string }>(
      `/admin/admin-smalls/${encodeURIComponent(accountId)}/`, { method: "DELETE" },
    ),
  adminBigProfile: (slug: string) => apiRequest<Record<string, unknown>>(`/admin/admin-bigs/profile/${encodeURIComponent(slug)}/`),
  updateAdminBigProfile: (slug: string, body: { current_password: string; username?: string; email?: string; slug?: string }) =>
    apiRequest<Record<string, unknown>>(`/admin/admin-bigs/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  createAdminSmallAvatarUploadIntent: (slug: string, setupToken: string) =>
    apiRequest<AdminAvatarUploadIntent>(`/admin/admin-smalls/${encodeURIComponent(slug)}/avatar/upload-intents/`, {
      method: "POST", body: jsonBody({ setup_token: setupToken }),
    }),
  completeAdminSmallAvatarUpload: (slug: string, body: { setup_token: string; intent_token: string; public_id: string }) =>
    apiRequest<{ account_id: string; role: "admin_small"; avatar_secure_url: string; complete: boolean; site_codes: string[] }>(
      `/admin/admin-smalls/${encodeURIComponent(slug)}/avatar/complete/`, { method: "POST", body: jsonBody(body) },
    ),
  teachers: (site_code?: string, options: { search?: string; status?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<PageResult<Teacher>>(`/admin/teachers/${query({ site_code, ...options })}`),
  teacherAssignmentOptions: (site_code?: string, options: { limit?: number; offset?: number } = {}) =>
    apiRequest<PageResult<Pick<Teacher, "teacher_id" | "full_name">> & { site_code: string }>(
      `/admin/teachers/assignment-options/${query({ site_code, ...options })}`,
    ),
  createTeacher: (body: { site_code?: string; full_name: string; email: string; username?: string; slug?: string; phone?: string; avatar_requested?: boolean }) =>
    apiRequest<Teacher & AccountReplication & { must_change_password: boolean; avatar_setup_token: string | null }>("/admin/teachers/", { method: "POST", body: jsonBody(body) }),
  sendTeacherCredentials: (slug: string, site_code: string) =>
    apiRequest<{ status: "sent"; email: string; detail: string }>(
      `/admin/teachers/${encodeURIComponent(slug)}/credential-email/${query({ site_code })}`,
      { method: "POST", body: jsonBody({}) },
    ),
  createTeacherAvatarUploadIntent: (slug: string, setupToken: string) =>
    apiRequest<AdminAvatarUploadIntent>(`/admin/teachers/${encodeURIComponent(slug)}/avatar/upload-intents/`, {
      method: "POST", body: jsonBody({ setup_token: setupToken }),
    }),
  completeTeacherAvatarUpload: (slug: string, body: { setup_token: string; intent_token: string; public_id: string }) =>
    apiRequest<{ account_id: string; role: "giao_vien"; avatar_secure_url: string; complete: boolean; site_codes: string[] }>(
      `/admin/teachers/${encodeURIComponent(slug)}/avatar/complete/`, { method: "POST", body: jsonBody(body) },
    ),
  teacher: (slug: string, site_code: string) => apiRequest<Teacher>(`/admin/teachers/${encodeURIComponent(slug)}/${query({ site_code })}`),
  deleteTeacher: (slug: string, site_code: string) => apiRequest<Record<string, unknown>>(`/admin/teachers/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "DELETE" }),
  setTeacherStatus: (slug: string, site_code: string, status: "active" | "inactive") =>
    apiRequest<Record<string, unknown>>(`/admin/teachers/${encodeURIComponent(slug)}/status/${query({ site_code })}`, { method: "PATCH", body: jsonBody({ status }) }),
  teacherProfile: (slug: string) => apiRequest<Teacher>(`/teachers/profile/${encodeURIComponent(slug)}/`),
  updateTeacherProfile: (slug: string, body: { full_name?: string; phone?: string | null }) =>
    apiRequest<Teacher>(`/teachers/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  employees: (site_code?: string, options: { job_title?: string; status?: string; search?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<PageResult<Employee>>(`/admin/employees/${query({ site_code, ...options })}`),
  createEmployee: (body: { site_code?: string; full_name: string; email: string; username?: string; phone?: string; job_title: Employee["job_title"]; avatar_requested?: boolean }) =>
    apiRequest<Employee & AccountReplication & { must_change_password: boolean; credential_email_status: NonNullable<Employee["credential_email_status"]>; avatar_setup_token: string | null }>("/admin/employees/", { method: "POST", body: jsonBody(body) }),
  sendEmployeeCredentials: (accountId: string, site_code: string) =>
    apiRequest<{ detail: string; email: string; status: "sent" }>(
      `/admin/employees/${encodeURIComponent(accountId)}/credential-email/${query({ site_code })}`,
      { method: "POST" },
    ),
  createEmployeeAvatarUploadIntent: (slug: string, setupToken: string) =>
    apiRequest<AdminAvatarUploadIntent>(`/admin/employees/${encodeURIComponent(slug)}/avatar/upload-intents/`, {
      method: "POST", body: jsonBody({ setup_token: setupToken }),
    }),
  completeEmployeeAvatarUpload: (slug: string, body: { setup_token: string; intent_token: string; public_id: string }) =>
    apiRequest<{ account_id: string; role: Employee["job_title"]; avatar_secure_url: string; complete: boolean; site_codes: string[] }>(
      `/admin/employees/${encodeURIComponent(slug)}/avatar/complete/`, { method: "POST", body: jsonBody(body) },
    ),
  employee: (slug: string, site_code: string) =>
    apiRequest<Employee>(`/admin/employees/${encodeURIComponent(slug)}/${query({ site_code })}`),
  updateEmployee: (slug: string, site_code: string, body: { full_name?: string; phone?: string | null; job_title?: Employee["job_title"] }) =>
    apiRequest<Employee>(`/admin/employees/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "PATCH", body: jsonBody(body) }),
  setEmployeeStatus: (slug: string, site_code: string) =>
    apiRequest<Record<string, unknown>>(`/admin/employees/${encodeURIComponent(slug)}/status/${query({ site_code })}`, { method: "PATCH", body: jsonBody({ status: "inactive" }) }),
  deleteEmployee: (slug: string, site_code: string) =>
    apiRequest<{ deleted: boolean; profile_retained: boolean; detail: string }>(`/admin/employees/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "DELETE" }),
  students: (options: { site_code?: string; status?: string; search?: string; account_issued?: boolean; limit?: number; offset?: number } = {}) =>
    apiRequest<ApiPage<Student>>(`/admin/students/${query(options)}`),
  courseRegistrations: (options: { site_code?: string; pending?: boolean; search?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<ApiPage<CourseRegistration>>(`/admin/course-registrations/${query(options)}`),
  createStudent: (body: StudentProfileWrite, site_code?: string) =>
    apiRequest<StudentProfile>(`/admin/students/${query({ site_code })}`, { method: "POST", body: jsonBody(body) }),
  student: (slug: string, site_code?: string) =>
    apiRequest<StudentProfile>(`/admin/students/${encodeURIComponent(slug)}/${query({ site_code })}`),
  updateStudent: (slug: string, body: Partial<StudentProfileWrite>, site_code?: string) =>
    apiRequest<StudentProfile>(`/admin/students/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "PATCH", body: jsonBody(body) }),
  createStudentAvatarUploadIntent: (slug: string, site_code?: string) =>
    apiRequest<AdminAvatarUploadIntent>(`/admin/students/${encodeURIComponent(slug)}/avatar/upload-intents/${query({ site_code })}`, { method: "POST", body: "{}" }),
  completeStudentAvatarUpload: (slug: string, body: { intent_token: string; public_id: string }, site_code?: string) =>
    apiRequest<{ student_id: string; slug: string; site_code: string; avatar_secure_url: string; complete: boolean }>(
      `/admin/students/${encodeURIComponent(slug)}/avatar/complete/${query({ site_code })}`, { method: "POST", body: jsonBody(body) },
    ),
  issueStudentAccount: (slug: string, site_code?: string) =>
    apiRequest<AccountReplication & { username: string; email: string; email_sent: boolean; must_change_password: boolean }>(`/admin/students/${encodeURIComponent(slug)}/account/${query({ site_code })}`, { method: "POST", body: "{}" }),
  deleteStudent: (slug: string, site_code?: string) => apiRequest<{ student_id: string; slug: string; site_code: string; deleted: boolean }>(`/admin/students/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "DELETE" }),
  updateSubject: (slug: string, body: { ten_mon?: string; mo_ta?: string | null }) =>
    apiRequest<Record<string, unknown>>(`/admin/shared/subjects/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  notifications: (options: { site_code?: string; category?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<AdminNotificationList>(`/admin/notifications/${query(options)}`),
  createNotification: (body: CreateAdminNotification, idempotencyKey: string) =>
    apiRequest<AdminNotificationCreateResponse>("/admin/notifications/", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: jsonBody(body),
    }),
  auditLogs: (options: { site_code?: string; account_id?: string; log_type?: string; from_date?: string; to_date?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<AdminAuditLogList>(`/reports/audit-logs/${query({
      ma_co_so: options.site_code,
      ma_tai_khoan: options.account_id,
      loai_log: options.log_type,
      tu_ngay: options.from_date,
      den_ngay: options.to_date,
      limit: options.limit,
      offset: options.offset,
    })}`),
};
