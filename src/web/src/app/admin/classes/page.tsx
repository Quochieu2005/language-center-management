import ClassesPage from "@/components/admin/classes/ClassesPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small", "le_tan", "xep_lop", "tu_van"]}><ClassesPage /></RequireSession>;
}

