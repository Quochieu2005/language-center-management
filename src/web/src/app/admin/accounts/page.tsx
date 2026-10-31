import AccountsPage from "@/components/admin/accounts/AccountsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><AccountsPage /></RequireSession>;
}

