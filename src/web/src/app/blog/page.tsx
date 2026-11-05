import type { Metadata } from "next";
import { BlogPage } from "@/components/web/catalog/PublicInfoPage";

export const metadata: Metadata = { title: "Blog học tập | [Tên trung tâm]", description: "Gợi ý phương pháp học ngoại ngữ." };
export default function Page() { return <BlogPage />; }
