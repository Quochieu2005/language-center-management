import { apiRequest } from "./client";

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

export const catalogApi = {
  publicCourses: () => apiRequest<PublicCourseList>("/courses/"),
};
