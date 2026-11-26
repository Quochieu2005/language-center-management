import AdminLayout from "@/components/admin/layout/AdminLayout";
import type { ReactNode } from "react";
import { RequireSession } from "@/lib/auth/session";
import { BRAND_NAME } from "@/lib/brand";

export const metadata = {
  title: `Quản trị | ${BRAND_NAME}`,
  description: "Bảng điều khiển quản trị hệ thống CSDL phân tán",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <RequireSession roles={["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan"]}><AdminLayout>{children}</AdminLayout></RequireSession>;
}

