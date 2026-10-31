"use client";

import { Alert, Empty, Spin, Table, Typography, type TableProps } from "antd";
import type { ApiRow } from "@/lib/api/academics";

export function ApiErrorNotice({ error }: { error: unknown }) {
  const detail = error instanceof Error ? error.message : "Không tải được dữ liệu từ API.";
  return <Alert type="error" showIcon title="Không thể hoàn tất yêu cầu" description={detail} />;
}

export function ApiDataTable({ rows, loading, emptyText = "Chưa có dữ liệu", onRow }: {
  rows: ApiRow[]; loading?: boolean; emptyText?: string; onRow?: TableProps<ApiRow>["onRow"];
}) {
  const keys = rows.length ? Object.keys(rows[0]).filter((key) => !["password", "password_hash"].includes(key)) : [];
  const columns = keys.map((key) => ({
    title: key.replaceAll("_", " "), dataIndex: key, key, ellipsis: true,
    render: (value: unknown) => <Typography.Text>{formatValue(value)}</Typography.Text>,
  }));
  return <Table<ApiRow> rowKey={(row, index) => String(row.id ?? row.slug ?? row.account_id ?? row.student_id ?? row.class_id ?? row.enrollment_id ?? row.session_id ?? row.tuition_id ?? row.transfer_id ?? index)} size="middle" loading={loading} dataSource={rows} columns={columns} onRow={onRow} locale={{ emptyText: <Empty description={emptyText} /> }} scroll={{ x: "max-content" }} pagination={{ pageSize: 10, showSizeChanger: false }} />;
}

export function LoadingPanel({ text = "Đang tải dữ liệu từ API..." }: { text?: string }) {
  return <div style={{ minHeight: 180, display: "grid", placeItems: "center" }}><Spin description={text} /></div>;
}

export function asRows(value: unknown): ApiRow[] {
  if (Array.isArray(value)) return value.filter(isRow);
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (Array.isArray(record.results)) return record.results.filter(isRow);
    return [record];
  }
  return [];
}

function isRow(value: unknown): value is ApiRow {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
