import type { AvatarUploadIntent } from "./auth";
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
  cover_url?: string | null;
};

export type BlogArticle = BlogArticleSummary & { content: string; cover_public_id?: string | null };
export type PublicBlogArticle = {
  slug: string;
  title: string;
  excerpt: string;
  content: string;
  reading_time_minutes: number;
  published_at: string | null;
  category: { slug: string; name: string };
  cover_url: string | null;
};
export type PublicBlogArticleSummary = Omit<PublicBlogArticle, "content">;
export type BlogCategoryInput = Pick<BlogCategory, "slug" | "name" | "description" | "status">;
export type BlogArticleInput = Omit<BlogArticle, "published_at" | "cover_url"> & { published_at: string | null; cover_url?: string | null };
export type BlogSyncStatus = { pending_count: number; review_count: number; completed?: number };
export type BlogImageKind = "cover" | "content";

export type BlogWriteResult = {
  scope: "REPLICATED-WRITE";
  complete: boolean;
  site_codes: string[];
  missing_sites: string[];
  idempotent_replay: boolean;
  result: Record<string, unknown>;
};

type BlogDetail<T> = { scope: "GLOBAL"; complete: boolean; site_codes: string[]; result: T };
type PublicBlogDetail = BlogDetail<PublicBlogArticle>;

export const blogApi = {
  imageIntent: (slug: string, kind: BlogImageKind) => apiRequest<AvatarUploadIntent>("/admin/blog/images/upload-intents/", {
    method: "POST", body: jsonBody({ slug, kind }),
  }),
  imageComplete: (body: { intent_token: string; public_id: string }) => apiRequest<{ public_id: string; secure_url: string }>("/admin/blog/images/complete/", {
    method: "POST", body: jsonBody(body),
  }),
  syncStatus: () => apiRequest<BlogSyncStatus>("/admin/blog/sync/"),
  runSync: () => apiRequest<BlogSyncStatus>("/admin/blog/sync/", { method: "POST", body: "{}" }),
  publicArticles: () => apiRequest<BlogList<PublicBlogArticleSummary>>("/blog/articles/"),
  publicArticle: (slug: string) => apiRequest<PublicBlogDetail>(`/blog/${encodeURIComponent(slug)}/`),
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
