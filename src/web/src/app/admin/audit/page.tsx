import AuditPage from "@/components/admin/audit/AuditPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><AuditPage /></RequireSession>;
}

