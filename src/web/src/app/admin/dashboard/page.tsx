import DashboardPage from "@/components/admin/dashboard/DashboardPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan", "xep_lop"]}><DashboardPage /></RequireSession>;
}

