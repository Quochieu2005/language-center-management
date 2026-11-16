"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, App, Button, Card, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ApiError } from "@/lib/api/client";
import BlogContentEditor from "./BlogContentEditor";
import styles from "./BlogPage.module.scss";
import {
  blogApi, type BlogArticleInput, type BlogArticleSummary,
  type BlogCategory, type BlogCategoryInput, type BlogList, type BlogWriteResult,
} from "@/lib/api/blog";

type CategoryForm = BlogCategoryInput;
type ArticleForm = Omit<BlogArticleInput, "published_at"> & { published_at?: string };
type Editor = { kind: "category" | "article"; slug?: string } | null;
type WriteOperation =
  | { kind: "category-create"; key: string; body: CategoryForm }
  | { kind: "category-update"; key: string; slug: string; body: CategoryForm }
  | { kind: "category-delete"; key: string; slug: string }
  | { kind: "article-create"; key: string; body: BlogArticleInput }
  | { kind: "article-update"; key: string; slug: string; body: BlogArticleInput }
  | { kind: "article-delete"; key: string; slug: string };
type PendingWrite = { operation: WriteOperation; missingSites: string[] };

const pendingStorageKey = "admin-blog-pending-write";
const categoryStatus = { hoat_dong: "Đang hoạt động", ngung: "Ngừng" };
const articleStatus = { nhap: "Bản nháp", da_xuat_ban: "Đã xuất bản", an: "Đã ẩn" };
const slugRule = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
function articleSlug(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "d")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 160).replace(/-+$/g, "");
}
const vietnamDate = new Intl.DateTimeFormat("vi-VN", {
  dateStyle: "short", timeZone: "Asia/Ho_Chi_Minh",
});

function toLocalDate(value: string | null) {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(date).map(({ type, value: part }) => [type, part]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function toUtcDateTime(value?: string) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00+07:00`);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function readPendingWrite(): PendingWrite | null {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(pendingStorageKey) || "null");
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return null;
    const item = saved as { operation?: Record<string, unknown>; missingSites?: unknown };
    const operation = item.operation;
    const kinds = ["category-create", "category-update", "category-delete", "article-create", "article-update", "article-delete"];
    if (!operation || typeof operation.kind !== "string" || !kinds.includes(operation.kind)
      || typeof operation.key !== "string" || !/^[\da-f-]{36}$/i.test(operation.key)
      || !Array.isArray(item.missingSites) || !item.missingSites.every((site) => typeof site === "string")) {
      sessionStorage.removeItem(pendingStorageKey);
      return null;
    }
    if (operation.kind.endsWith("-delete")) {
      if (typeof operation.slug !== "string" || !slugRule.test(operation.slug)) {
        sessionStorage.removeItem(pendingStorageKey);
        return null;
      }
    } else if (!operation.body || typeof operation.body !== "object" || Array.isArray(operation.body)) {
      sessionStorage.removeItem(pendingStorageKey);
      return null;
    }
    return saved as PendingWrite;
  } catch {
    return null;
  }
}

export default function BlogPage() {
  const { message, modal } = App.useApp();
  const [categoryList, setCategoryList] = useState<BlogList<BlogCategory> | null>(null);
  const [articleList, setArticleList] = useState<BlogList<BlogArticleSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadingArticle, setLoadingArticle] = useState("");
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<Editor>(null);
  const [pending, setPending] = useState<PendingWrite | null>(null);
  const [categoryForm] = Form.useForm<CategoryForm>();
  const [articleForm] = Form.useForm<ArticleForm>();
  const articleSlugManuallyEdited = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setCategoryList(null);
    setArticleList(null);
    try {
      const [categories, articles] = await Promise.all([blogApi.categories(), blogApi.articles()]);
      setCategoryList(categories);
      setArticleList(articles);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được dữ liệu Blog.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const restored = readPendingWrite();
    queueMicrotask(() => {
      if (restored) setPending(restored);
      void load();
    });
  }, [load]);

  const savePending = (value: PendingWrite | null) => {
    setPending(value);
    try {
      if (value) sessionStorage.setItem(pendingStorageKey, JSON.stringify(value));
      else sessionStorage.removeItem(pendingStorageKey);
    } catch {
      // shortcut: blocked session storage keeps retry available only until this page closes.
    }
  };

  const finishEditor = () => {
    setEditor(null);
    categoryForm.resetFields();
    articleForm.resetFields();
  };

  const runWrite = async (operation: WriteOperation) => {
    setSaving(true);
    setError("");
    try {
      let result: BlogWriteResult;
      switch (operation.kind) {
        case "category-create": result = await blogApi.createCategory(operation.body, operation.key); break;
        case "category-update": result = await blogApi.updateCategory(operation.slug, operation.body, operation.key); break;
        case "category-delete": result = await blogApi.deleteCategory(operation.slug, operation.key); break;
        case "article-create": result = await blogApi.createArticle(operation.body, operation.key); break;
        case "article-update": result = await blogApi.updateArticle(operation.slug, operation.body, operation.key); break;
        case "article-delete": result = await blogApi.deleteArticle(operation.slug, operation.key); break;
      }
      if (!result.complete) {
        savePending({ operation, missingSites: result.missing_sites });
        finishEditor();
        message.warning("Blog chưa đồng bộ đủ cơ sở. Dùng nút thử lại để tiếp tục đúng yêu cầu này.");
        void load();
        return;
      }
      savePending(null);
      finishEditor();
      message.success("Đã đồng bộ thay đổi Blog tới các cơ sở.");
      await load();
    } catch (reason) {
      const retryable = !(reason instanceof ApiError) || reason.status >= 500;
      const missingSites = reason instanceof ApiError && Array.isArray(reason.payload.missing_sites)
        ? reason.payload.missing_sites.filter((site): site is string => typeof site === "string")
        : [];
      savePending(retryable ? { operation, missingSites } : null);
      setError(reason instanceof Error ? reason.message : "Chưa xác nhận được kết quả ghi Blog.");
      if (retryable) finishEditor();
    } finally {
      setSaving(false);
    }
  };

  const dataComplete = Boolean(categoryList?.complete && articleList?.complete && !loading);
  const canWrite = dataComplete && !pending && !saving;
  const activeCategories = categoryList?.results.filter((item) => item.status === "hoat_dong") ?? [];

  const openCategory = (row?: BlogCategory) => {
    categoryForm.resetFields();
    if (row) categoryForm.setFieldsValue({ slug: row.slug, name: row.name, description: row.description ?? "", status: row.status });
    else categoryForm.setFieldsValue({ status: "hoat_dong", description: "" });
    setEditor({ kind: "category", slug: row?.slug });
  };

  const openArticle = async (row?: BlogArticleSummary) => {
    articleForm.resetFields();
    if (!row) {
      articleSlugManuallyEdited.current = false;
      articleForm.setFieldsValue({ status: "nhap", reading_time_minutes: 5, published_at: toLocalDate(new Date().toISOString()) });
      setEditor({ kind: "article" });
      return;
    }
    setLoadingArticle(row.slug);
    try {
      const { result } = await blogApi.article(row.slug);
      articleForm.setFieldsValue({ ...result, published_at: toLocalDate(result.published_at) });
      articleSlugManuallyEdited.current = result.slug !== articleSlug(result.title);
      setEditor({ kind: "article", slug: row.slug });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được nội dung bài viết.");
    } finally {
      setLoadingArticle("");
    }
  };

  const submitCategory = (values: CategoryForm) => {
    if (!canWrite) return;
    const body = { ...values, slug: values.slug.trim(), name: values.name.trim(), description: values.description?.trim() || null };
    const key = crypto.randomUUID();
    void runWrite(editor?.slug
      ? { kind: "category-update", key, slug: editor.slug, body }
      : { kind: "category-create", key, body });
  };

  const submitArticle = (values: ArticleForm) => {
    if (!canWrite) return;
    const body: BlogArticleInput = {
      slug: values.slug.trim(), category_slug: values.category_slug, title: values.title.trim(),
      excerpt: values.excerpt.trim(), content: values.content.trim(),
      reading_time_minutes: values.reading_time_minutes, status: values.status,
      published_at: toUtcDateTime(values.published_at),
    };
    const key = crypto.randomUUID();
    void runWrite(editor?.slug
      ? { kind: "article-update", key, slug: editor.slug, body }
      : { kind: "article-create", key, body });
  };

  const confirmDelete = (kind: "category" | "article", row: BlogCategory | BlogArticleSummary) => {
    const operation: WriteOperation = kind === "category"
      ? { kind: "category-delete", key: crypto.randomUUID(), slug: row.slug }
      : { kind: "article-delete", key: crypto.randomUUID(), slug: row.slug };
    modal.confirm({
      title: kind === "category" ? "Xóa danh mục Blog?" : "Xóa bài viết Blog?",
      content: kind === "category"
        ? "Danh mục chỉ xóa được khi không còn bài viết tham chiếu. Thay đổi được gửi tới tất cả cơ sở đang hoạt động."
        : "Bài viết sẽ bị xóa khỏi tất cả cơ sở đang hoạt động sau khi đồng bộ hoàn tất.",
      okText: "Xóa vĩnh viễn", cancelText: "Hủy", okButtonProps: { danger: true, loading: saving },
      onOk: () => runWrite(operation),
    });
  };

  const categoryColumns: ColumnsType<BlogCategory> = [
    { title: "Danh mục", dataIndex: "name", render: (name, row) => <><strong>{name}</strong><br /><span>/{row.slug}</span></> },
    { title: "Mô tả", dataIndex: "description", render: (value) => value || "—" },
    { title: "Bài viết", dataIndex: "post_count" },
    { title: "Trạng thái", dataIndex: "status", render: (value: BlogCategory["status"]) => <Tag color={value === "hoat_dong" ? "green" : "default"}>{categoryStatus[value]}</Tag> },
    { title: "Thao tác", render: (_, row) => <Space><Button size="small" disabled={!canWrite} onClick={() => openCategory(row)}>Sửa</Button><Button danger size="small" disabled={!canWrite || row.post_count > 0} title={row.post_count > 0 ? "Danh mục đang được bài viết sử dụng." : undefined} onClick={() => confirmDelete("category", row)}>Xóa</Button></Space> },
  ];

  const articleColumns: ColumnsType<BlogArticleSummary> = [
    { title: "Bài viết", dataIndex: "title", render: (title, row) => <><strong>{title}</strong><br /><span>/{row.slug}</span></> },
    { title: "Danh mục", dataIndex: "category_slug" },
    { title: "Tóm tắt", dataIndex: "excerpt" },
    { title: "Thời gian đọc", dataIndex: "reading_time_minutes", render: (value) => `${value} phút` },
    { title: "Trạng thái", dataIndex: "status", render: (value: BlogArticleSummary["status"]) => <Tag color={value === "da_xuat_ban" ? "green" : value === "an" ? "default" : "gold"}>{articleStatus[value]}</Tag> },
    { title: "Ngày xuất bản", dataIndex: "published_at", render: (value: string | null) => value ? vietnamDate.format(new Date(value)) : "Ngay khi xuất bản" },
    { title: "Thao tác", render: (_, row) => <Space><Button size="small" disabled={!canWrite} loading={loadingArticle === row.slug} onClick={() => void openArticle(row)}>Sửa</Button><Button danger size="small" disabled={!canWrite} onClick={() => confirmDelete("article", row)}>Xóa</Button></Space> },
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon title={error} />}
    {categoryList && !categoryList.complete && <Alert type="warning" showIcon title="Danh mục Blog chưa được đối chiếu đủ các cơ sở. Thao tác ghi đang bị khóa." description={`Site thiếu: ${categoryList.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${categoryList.inconsistent_sites.join(", ") || "không có"}.`} />}
    {articleList && !articleList.complete && <Alert type="warning" showIcon title="Bài viết Blog chưa được đối chiếu đủ các cơ sở. Thao tác ghi đang bị khóa." description={`Site thiếu: ${articleList.missing_sites.join(", ") || "không có"}. Site lệch dữ liệu: ${articleList.inconsistent_sites.join(", ") || "không có"}.`} />}
    {pending && <Alert type="warning" showIcon title="Yêu cầu Blog chưa đồng bộ hoàn tất" description={<Space orientation="vertical"><span>Site chưa xác nhận: {pending.missingSites.join(", ") || "chưa xác định; API chưa xác nhận kết quả"}. Giữ nguyên mã yêu cầu và nội dung khi thử lại.</span><Button size="small" loading={saving} onClick={() => void runWrite(pending.operation)}>Thử lại đúng yêu cầu</Button></Space>} />}
    <Card title={`Quản lý Blog${categoryList && articleList ? ` · ${categoryList.count} danh mục · ${articleList.count} bài viết` : ""}`} extra={<Space><Button disabled={loading || saving} onClick={() => void load()}>Tải lại</Button><Button type="primary" disabled={!canWrite || !activeCategories.length} onClick={() => openArticle()}>Tạo bài viết</Button><Button type="primary" disabled={!canWrite} onClick={() => openCategory()}>Tạo danh mục</Button></Space>}>
      {categoryList && articleList && <div style={{ marginBottom: 12 }}><Tag color={dataComplete ? "green" : "orange"}>{dataComplete ? "Đã đối chiếu đầy đủ" : "Chưa đồng bộ đủ"}</Tag><span>Các site: {categoryList.site_codes.join(", ") || "Chưa có dữ liệu"}</span></div>}
      <Tabs defaultActiveKey="articles" items={[
        { key: "articles", label: `Bài viết (${articleList?.count ?? 0})`, children: <Table<BlogArticleSummary> rowKey="slug" loading={loading} columns={articleColumns} dataSource={articleList?.results ?? []} scroll={{ x: 980 }} locale={{ emptyText: <Empty description="Chưa có bài viết Blog." /> }} pagination={{ pageSize: 10 }} /> },
        { key: "categories", label: `Danh mục (${categoryList?.count ?? 0})`, children: <Table<BlogCategory> rowKey="slug" loading={loading} columns={categoryColumns} dataSource={categoryList?.results ?? []} scroll={{ x: 760 }} locale={{ emptyText: <Empty description="Chưa có danh mục Blog." /> }} pagination={{ pageSize: 10 }} /> },
      ]} />
    </Card>

    <Modal title={editor?.slug ? "Sửa danh mục Blog" : "Tạo danh mục Blog"} open={editor?.kind === "category"} onCancel={finishEditor} footer={null} destroyOnHidden>
      <Form form={categoryForm} layout="vertical" onFinish={submitCategory}>
        <Form.Item name="name" label="Tên danh mục" rules={[{ required: true }, { max: 100 }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="slug" label="Slug" extra="Dùng chữ thường, số và dấu gạch nối; đường dẫn bài viết sẽ dựa trên slug riêng của bài." rules={[{ required: true }, { max: 120 }, { pattern: slugRule, message: "Slug chỉ gồm chữ thường, số và dấu gạch nối đơn." }]}><Input maxLength={120} /></Form.Item>
        <Form.Item name="description" label="Mô tả"><Input.TextArea rows={3} maxLength={500} /></Form.Item>
        <Form.Item name="status" label="Trạng thái" rules={[{ required: true }]}><Select options={[{ value: "hoat_dong", label: "Đang hoạt động" }, { value: "ngung", label: "Ngừng" }]} /></Form.Item>
        <Button type="primary" htmlType="submit" block loading={saving}>{editor?.slug ? "Lưu và đồng bộ" : "Tạo và đồng bộ"}</Button>
      </Form>
    </Modal>

    <Modal title={editor?.slug ? "Sửa bài viết Blog" : "Tạo bài viết Blog"} open={editor?.kind === "article"} onCancel={finishEditor} footer={null} width="min(1120px, calc(100vw - 32px))" destroyOnHidden>
      <Form form={articleForm} layout="vertical" onFinish={submitArticle}>
        <div className={styles.articleIdentityFields}>
          <Form.Item name="title" label="Tiêu đề" rules={[{ required: true }, { max: 200 }]}><Input maxLength={200} onChange={(event) => {
            if (!articleSlugManuallyEdited.current) articleForm.setFieldValue("slug", articleSlug(event.target.value));
          }} /></Form.Item>
          <Form.Item name="slug" label="Slug bài viết" extra="Tự tạo từ tiêu đề; bạn có thể tự sửa. Bài viết cũ giữ URL nếu slug đã được tùy chỉnh." rules={[{ required: true }, { max: 160 }, { pattern: slugRule, message: "Slug chỉ gồm chữ thường, số và dấu gạch nối đơn." }]}><Input maxLength={160} onChange={(event) => {
            const slug = event.target.value;
            articleSlugManuallyEdited.current = Boolean(slug) && slug !== articleSlug(articleForm.getFieldValue("title") || "");
            if (!slug) articleForm.setFieldValue("slug", articleSlug(articleForm.getFieldValue("title") || ""));
          }} /></Form.Item>
        </div>
        <div className={styles.articleMetaFields}>
          <Form.Item name="category_slug" label="Danh mục" rules={[{ required: true }]}><Select options={activeCategories.map((category) => ({ value: category.slug, label: category.name }))} placeholder="Chọn danh mục đang hoạt động" /></Form.Item>
          <Form.Item name="reading_time_minutes" label="Thời gian đọc (phút)" rules={[{ required: true }]}><InputNumber min={1} max={240} precision={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="status" label="Trạng thái" rules={[{ required: true }]}><Select options={[{ value: "nhap", label: "Bản nháp" }, { value: "da_xuat_ban", label: "Đã xuất bản" }, { value: "an", label: "Đã ẩn" }]} /></Form.Item>
          <Form.Item name="published_at" label="Ngày xuất bản" extra="Mặc định là ngày tạo; để trống nếu xuất bản ngay khi bật trạng thái."><Input type="date" /></Form.Item>
        </div>
        <Form.Item name="excerpt" label="Tóm tắt" rules={[{ required: true }, { max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item>
        <Form.Item name="content" label="Nội dung chi tiết" rules={[{ required: true }, { max: 20000 }]}><BlogContentEditor /></Form.Item>
        <Button type="primary" htmlType="submit" block loading={saving}>{editor?.slug ? "Lưu và đồng bộ" : "Tạo và đồng bộ"}</Button>
      </Form>
    </Modal>
  </Space>;
}
