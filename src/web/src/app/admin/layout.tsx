import AdminLayout from "@/components/admin/layout/AdminLayout";
import type { ReactNode } from "react";
import { RequireSession } from "@/lib/auth/session";

export const metadata = {
  title: "Admin Dashboard - Quản lý trung tâm ngoại ngữ (Zenith Theme)",
  description: "Bảng điều khiển quản trị hệ thống CSDL phân tán",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <RequireSession roles={["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan", "xep_lop"]}><AdminLayout>{children}</AdminLayout></RequireSession>;
}

