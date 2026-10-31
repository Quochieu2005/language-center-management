import TuitionPage from "@/components/admin/tuition/TuitionPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small", "ke_toan"]}><TuitionPage /></RequireSession>;
}

