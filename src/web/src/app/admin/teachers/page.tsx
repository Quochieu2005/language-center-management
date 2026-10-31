import TeachersPage from "@/components/admin/teachers/TeachersPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><TeachersPage /></RequireSession>;
}

