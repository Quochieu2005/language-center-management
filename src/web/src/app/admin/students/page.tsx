import StudentsPage from "@/components/admin/students/StudentsPage";
import { RequireSession } from "@/lib/auth/session";

export default async function Page({ searchParams }: { searchParams: Promise<{ search?: string }> }) {
  const { search = "" } = await searchParams;
  return <RequireSession roles={["admin_big", "admin_small", "ke_toan", "tu_van"]}><StudentsPage key={search} initialSearch={search} /></RequireSession>;
}

