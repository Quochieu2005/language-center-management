import { RequireSession } from "@/lib/auth/session";
import CoursesPage from "@/components/admin/courses/CoursesPage";

export default function Page() {
  return <RequireSession roles={["admin_big", "tu_van", "ke_toan"]}><CoursesPage /></RequireSession>;
}
