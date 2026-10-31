import TransfersPage from "@/components/admin/transfers/TransfersPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><TransfersPage /></RequireSession>;
}

