import { apiRequest, jsonBody, query } from "./client";

export type PageResult<T> = { count: number; limit: number; offset: number; results: T[]; site_code?: string };
export type SiteCounts = {
  scope: "LOCAL" | "GLOBAL";
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  total_active_students: number;
  results: { site_code: string; active_students: number }[];
};
export type AdminSmall = {
  admin_id: string; site_code: string; full_name: string; phone: string | null;
  account_id: string; slug: string; username: string; email: string;
  account_status: "active" | "inactive"; profile_status: "dang_lam" | "nghi_viec";
};
export type Teacher = {
  teacher_id: string; account_id: string | null; slug: string | null; site_code: string;
  account_status: "active" | "inactive" | null; full_name: string; phone: string | null;
  email: string | null; username: string | null; specialty: string;
  status: "dang_day" | "tam_nghi" | "nghi_viec";
};
export type Employee = {
  employee_id: string; account_id: string; slug: string; username: string; email: string;
  site_code: string; job_title: "le_tan" | "tu_van" | "ke_toan" | "xep_lop";
  full_name: string; phone: string | null; account_status: "active" | "inactive";
  employee_status: "dang_lam" | "nghi_viec";
};
export type Student = {
  student_id: string; slug: string; site_code: string; full_name: string;
  phone: string | null; email: string | null; status: string; account_issued: boolean;
};
export type ApiPage<T> = PageResult<T> & { complete?: boolean; missing_sites?: string[]; site_codes?: string[] };
export type AdminAvatarUploadIntent = {
  intent_token: string;
  upload_url: string;
  cloud_name: string;
  api_key: string;
  fields: Record<string, string>;
  max_file_bytes: number;
};

export const adminApi = {
  studentCounts: (site_code?: string) => apiRequest<SiteCounts>(`/admin/reports/students-by-site/${query({ site_code })}`),
  adminSmalls: (site_code?: string, limit = 100, offset = 0) =>
    apiRequest<PageResult<AdminSmall> & { complete: boolean; missing_sites: string[]; site_codes: string[] }>(
      `/admin/admin-smalls/${query({ site_code, limit, offset })}`,
    ),
  createAdminSmall: (body: { full_name: string; email: string; site_code: string; username?: string }) =>
    apiRequest<{ account_id: string; admin_id: string; username: string; email: string; site_code: string; slug: string; account_status: "active"; role: "admin_small"; must_change_password: boolean }>("/admin/admin-smalls/", { method: "POST", body: jsonBody(body) }),
  adminSmallProfile: (slug: string) => apiRequest<Record<string, unknown>>(`/admin/admin-smalls/profile/${encodeURIComponent(slug)}/`),
  updateAdminSmallProfile: (slug: string, body: { full_name?: string; phone?: string | null }) =>
    apiRequest<Record<string, unknown>>(`/admin/admin-smalls/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  updateAdminSmallStatus: (slug: string, status: "active" | "inactive") =>
    apiRequest<Record<string, unknown>>(`/admin/admin-smalls/${encodeURIComponent(slug)}/status/`, { method: "PATCH", body: jsonBody({ status }) }),
  deactivateAdminSmall: (accountId: string) =>
    apiRequest<Record<string, unknown>>(`/admin/admin-smalls/${encodeURIComponent(accountId)}/`, { method: "DELETE" }),
  adminBigProfile: (slug: string) => apiRequest<Record<string, unknown>>(`/admin/admin-bigs/profile/${encodeURIComponent(slug)}/`),
  updateAdminBigProfile: (slug: string, body: { current_password: string; username?: string; email?: string; slug?: string }) =>
    apiRequest<Record<string, unknown>>(`/admin/admin-bigs/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  createAdminAvatarUploadIntent: (slug: string) =>
    apiRequest<AdminAvatarUploadIntent>(`/admin/profile/${encodeURIComponent(slug)}/avatar/upload-intents/`, { method: "POST", body: "{}" }),
  completeAdminAvatarUpload: (slug: string, body: { intent_token: string; public_id: string }) =>
    apiRequest<{ account_id: string; role: "admin_big" | "admin_small"; avatar_secure_url: string; complete: boolean; site_codes: string[] }>(
      `/admin/profile/${encodeURIComponent(slug)}/avatar/complete/`, { method: "POST", body: jsonBody(body) },
    ),
  teachers: (site_code: string, options: { search?: string; status?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<PageResult<Teacher>>(`/admin/teachers/${query({ site_code, ...options })}`),
  createTeacher: (body: { site_code?: string; full_name: string; email: string; username?: string; phone?: string; specialty: string }) =>
    apiRequest<Teacher>("/admin/teachers/", { method: "POST", body: jsonBody(body) }),
  teacher: (slug: string, site_code: string) => apiRequest<Teacher>(`/admin/teachers/${encodeURIComponent(slug)}/${query({ site_code })}`),
  deleteTeacher: (slug: string, site_code: string) => apiRequest<Record<string, unknown>>(`/admin/teachers/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "DELETE" }),
  setTeacherStatus: (slug: string, site_code: string, status: "active" | "inactive") =>
    apiRequest<Record<string, unknown>>(`/admin/teachers/${encodeURIComponent(slug)}/status/${query({ site_code })}`, { method: "PATCH", body: jsonBody({ status }) }),
  teacherProfile: (slug: string) => apiRequest<Teacher>(`/teachers/profile/${encodeURIComponent(slug)}/`),
  updateTeacherProfile: (slug: string, body: { full_name?: string; phone?: string | null; specialty?: string }) =>
    apiRequest<Teacher>(`/teachers/profile/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  employees: (site_code: string, options: { job_title?: string; status?: string; search?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<PageResult<Employee>>(`/admin/employees/${query({ site_code, ...options })}`),
  createEmployee: (body: { site_code?: string; full_name: string; email: string; username?: string; phone?: string; job_title: Employee["job_title"] }) =>
    apiRequest<Employee>("/admin/employees/", { method: "POST", body: jsonBody(body) }),
  deleteEmployee: (slug: string, site_code: string) =>
    apiRequest<Record<string, unknown>>(`/admin/employees/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "DELETE" }),
  students: (options: { site_code?: string; status?: string; search?: string; account_issued?: boolean; limit?: number; offset?: number } = {}) =>
    apiRequest<ApiPage<Student>>(`/admin/students/${query(options)}`),
  issueStudentAccount: (slug: string) => apiRequest<Record<string, unknown>>(`/admin/students/${encodeURIComponent(slug)}/account/`, { method: "POST", body: "{}" }),
  deleteStudent: (slug: string, site_code?: string) => apiRequest<Record<string, unknown>>(`/admin/students/${encodeURIComponent(slug)}/${query({ site_code })}`, { method: "DELETE" }),
  updateSubject: (slug: string, body: { ten_mon?: string; mo_ta?: string | null }) =>
    apiRequest<Record<string, unknown>>(`/admin/shared/subjects/${encodeURIComponent(slug)}/`, { method: "PATCH", body: jsonBody(body) }),
  notifications: (options: { site_code?: string; category?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<{ complete: boolean; missing_sites: string[]; site_codes: string[]; count: number; limit: number; offset: number; results: Record<string, unknown>[] }>(`/admin/notifications/${query(options)}`),
};
