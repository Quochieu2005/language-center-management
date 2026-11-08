import { apiRequest, jsonBody, query } from "./client";

export type PublicCourse = {
  course_id: string;
  slug: string;
  subject_id: string;
  subject_slug: string;
  subject_name: string;
  name: string;
  level: string;
  session_count: number;
  standard_fee: number;
  version: number;
  branches: { site_code: string; site_name: string; open_class_count: number }[];
};

export type PublicCourseList = {
  scope: "GLOBAL";
  complete: boolean;
  site_codes: string[];
  missing_sites: string[];
  inconsistent_sites: string[];
  count: number;
  results: PublicCourse[];
};

export type PublicCourseClass = {
  class_id: string;
  site_code: string;
  name: string;
  start_date: string;
  end_date: string | null;
  schedule: string;
  start_time: string;
  end_time: string;
  remaining_seats: number;
};

export type PublicCourseClassList = {
  site_code: string;
  course_slug: string;
  count: number;
  results: PublicCourseClass[];
};

export type PublicEnrollmentResult = {
  site_code: string;
  class_id: string;
  accepted: boolean;
  already_registered: boolean;
  message: string;
};

export type SharedCourseCreateInput = {
  ma_khoa_hoc: string; slug?: string; ma_mon: string; ten_khoa_hoc: string;
  trinh_do: string; so_buoi: number; hoc_phi_chuan: number;
};
export type SharedCoursePatchInput = Omit<SharedCourseCreateInput, "ma_khoa_hoc" | "slug">;
export type SharedCourseWriteResult = {
  ma_khoa_hoc: string; slug: string; ma_mon: string; ten_khoa_hoc: string;
  trinh_do: string; so_buoi: number; hoc_phi_chuan: number; phien_ban: number;
  complete: boolean; sites: string[]; missing_sites: string[]; idempotent_replay: boolean;
};
export type SharedCourseDeleteResult = {
  ma_khoa_hoc: string; slug: string; deleted: boolean; complete: boolean;
  sites: string[]; missing_sites: string[]; idempotent_replay: boolean;
};

export const catalogApi = {
  publicCourses: () => apiRequest<PublicCourseList>("/courses/"),
  createCourse: (body: SharedCourseCreateInput, idempotencyKey: string) =>
    apiRequest<SharedCourseWriteResult>("/admin/courses/", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: jsonBody(body) }),
  updateCourse: (slug: string, body: SharedCoursePatchInput, idempotencyKey: string) =>
    apiRequest<SharedCourseWriteResult>(`/admin/courses/${encodeURIComponent(slug)}/`, { method: "PATCH", headers: { "Idempotency-Key": idempotencyKey }, body: jsonBody(body) }),
  deleteCourse: (slug: string, idempotencyKey: string) =>
    apiRequest<SharedCourseDeleteResult>(`/admin/courses/${encodeURIComponent(slug)}/`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey } }),
  publicClasses: (courseSlug: string, siteCode: string) => apiRequest<PublicCourseClassList>(
    `/courses/${encodeURIComponent(courseSlug)}/classes/${query({ site_code: siteCode })}`,
  ),
  publicEnroll: (body: { site_code: string; class_id: string; full_name: string; email: string; phone?: string }) =>
    apiRequest<PublicEnrollmentResult>("/public/enrollments/", { method: "POST", body: jsonBody(body) }),
};
