import AccountsPage from "@/components/admin/accounts/AccountsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big"]}><AccountsPage view="admin-smalls" /></RequireSession>;
}

