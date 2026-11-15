import { apiRequest, jsonBody } from "./client";

export type BlogList<T> = {
  scope: "GLOBAL";
  complete: boolean;
  site_codes: string[];
  missing_sites: string[];
  inconsistent_sites: string[];
  count: number;
  results: T[];
};

export type BlogCategory = {
  slug: string;
  name: string;
  description: string | null;
  status: "hoat_dong" | "ngung";
  post_count: number;
};

export type BlogArticleSummary = {
  slug: string;
  category_slug: string;
  title: string;
  excerpt: string;
  reading_time_minutes: number;
  status: "nhap" | "da_xuat_ban" | "an";
  published_at: string | null;
};

export type BlogArticle = BlogArticleSummary & { content: string };
export type BlogCategoryInput = Pick<BlogCategory, "slug" | "name" | "description" | "status">;
export type BlogArticleInput = Omit<BlogArticle, "published_at"> & { published_at: string | null };

export type BlogWriteResult = {
  scope: "REPLICATED-WRITE";
  complete: boolean;
  site_codes: string[];
  missing_sites: string[];
  idempotent_replay: boolean;
  result: Record<string, unknown>;
};

type BlogDetail<T> = { scope: "GLOBAL"; complete: boolean; site_codes: string[]; result: T };

export const blogApi = {
  categories: () => apiRequest<BlogList<BlogCategory>>("/admin/blog/categories/"),
  articles: () => apiRequest<BlogList<BlogArticleSummary>>("/admin/blog/articles/"),
  article: (slug: string) => apiRequest<BlogDetail<BlogArticle>>(`/admin/blog/articles/${encodeURIComponent(slug)}/`),
  createCategory: (body: BlogCategoryInput, key: string) => apiRequest<BlogWriteResult>("/admin/blog/categories/", {
    method: "POST", headers: { "Idempotency-Key": key }, body: jsonBody(body),
  }),
  updateCategory: (slug: string, body: BlogCategoryInput, key: string) => apiRequest<BlogWriteResult>(`/admin/blog/categories/${encodeURIComponent(slug)}/`, {
    method: "PATCH", headers: { "Idempotency-Key": key }, body: jsonBody(body),
  }),
  deleteCategory: (slug: string, key: string) => apiRequest<BlogWriteResult>(`/admin/blog/categories/${encodeURIComponent(slug)}/`, {
    method: "DELETE", headers: { "Idempotency-Key": key },
  }),
  createArticle: (body: BlogArticleInput, key: string) => apiRequest<BlogWriteResult>("/admin/blog/articles/", {
    method: "POST", headers: { "Idempotency-Key": key }, body: jsonBody(body),
  }),
  updateArticle: (slug: string, body: BlogArticleInput, key: string) => apiRequest<BlogWriteResult>(`/admin/blog/articles/${encodeURIComponent(slug)}/`, {
    method: "PATCH", headers: { "Idempotency-Key": key }, body: jsonBody(body),
  }),
  deleteArticle: (slug: string, key: string) => apiRequest<BlogWriteResult>(`/admin/blog/articles/${encodeURIComponent(slug)}/`, {
    method: "DELETE", headers: { "Idempotency-Key": key },
  }),
};
