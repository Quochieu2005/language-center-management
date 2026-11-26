import type { Metadata } from "next";
import { BlogPage } from "@/components/web/catalog/PublicInfoPage";
import { BRAND_NAME } from "@/lib/brand";

export const metadata: Metadata = { title: `Blog học tập | ${BRAND_NAME}`, description: "Gợi ý phương pháp học ngoại ngữ." };
export default function Page() { return <BlogPage />; }
