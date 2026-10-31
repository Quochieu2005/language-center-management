import AdminLayout from "@/components/admin/layout/AdminLayout";
import type { ReactNode } from "react";

export const metadata = {
  title: "Admin Dashboard - Quản lý trung tâm ngoại ngữ (Zenith Theme)",
  description: "Bảng điều khiển quản trị hệ thống CSDL phân tán",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <AdminLayout>{children}</AdminLayout>;
}

