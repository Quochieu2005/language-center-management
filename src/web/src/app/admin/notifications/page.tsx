import NotificationsPage from "@/components/admin/notifications/NotificationsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><NotificationsPage /></RequireSession>;
}
