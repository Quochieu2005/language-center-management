import { blogApi, type BlogImageKind } from "@/lib/api/blog";

export const BLOG_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

/** Signed intent from the API, direct upload to Cloudinary, then server-side verification. */
export async function uploadBlogImage(slug: string, kind: BlogImageKind, file: File) {
  if (!BLOG_IMAGE_TYPES.includes(file.type)) throw new Error("Chỉ nhận ảnh JPG, PNG hoặc WebP.");
  if (file.size < 1 || file.size > MAX_BYTES) throw new Error("Ảnh phải có dung lượng tối đa 5 MB.");
  const intent = await blogApi.imageIntent(slug, kind);
  const body = new FormData();
  body.append("file", file);
  body.append("api_key", intent.api_key);
  Object.entries(intent.fields).forEach(([key, value]) => body.append(key, value));
  const response = await fetch(intent.upload_url, { method: "POST", body, cache: "no-store" });
  const uploaded = (await response.json().catch(() => null)) as { public_id?: unknown } | null;
  if (!response.ok || typeof uploaded?.public_id !== "string") {
    throw new Error("Cloudinary không nhận được ảnh. Hãy kiểm tra cấu hình và thử lại.");
  }
  return blogApi.imageComplete({ intent_token: intent.intent_token, public_id: uploaded.public_id });
}
