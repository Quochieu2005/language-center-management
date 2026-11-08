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

export const catalogApi = {
  publicCourses: () => apiRequest<PublicCourseList>("/courses/"),
  publicClasses: (courseSlug: string, siteCode: string) => apiRequest<PublicCourseClassList>(
    `/courses/${encodeURIComponent(courseSlug)}/classes/${query({ site_code: siteCode })}`,
  ),
  publicEnroll: (body: { site_code: string; class_id: string; full_name: string; email: string; phone?: string }) =>
    apiRequest<PublicEnrollmentResult>("/public/enrollments/", { method: "POST", body: jsonBody(body) }),
};
