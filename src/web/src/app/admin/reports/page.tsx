import ReportsPage from "@/components/admin/reports/ReportsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><ReportsPage /></RequireSession>;
}

