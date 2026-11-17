import ContactsPage from "@/components/admin/contacts/ContactsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small", "tu_van"]}><ContactsPage /></RequireSession>;
}
