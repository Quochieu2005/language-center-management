import SubjectsPage from "@/components/admin/subjects/SubjectsPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big"]}><SubjectsPage /></RequireSession>;
}

