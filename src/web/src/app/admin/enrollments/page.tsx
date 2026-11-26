import CourseRegistrationsPage from "@/components/admin/enrollments/CourseRegistrationsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big", "admin_small", "tu_van"]}><CourseRegistrationsPage /></RequireSession>;
}
