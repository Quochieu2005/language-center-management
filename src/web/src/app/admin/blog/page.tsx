import BlogPage from "@/components/admin/blog/BlogPage";
import { RequireSession } from "@/lib/auth/session";

export default function Page() {
  return <RequireSession roles={["admin_big"]}><BlogPage /></RequireSession>;
}
