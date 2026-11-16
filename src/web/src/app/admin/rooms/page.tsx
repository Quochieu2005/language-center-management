import RoomsPage from "@/components/admin/rooms/RoomsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small"]}><RoomsPage /></RequireSession>;
}
