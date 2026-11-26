import type { Metadata } from "next";
import { ProgramsPage } from "@/components/web/catalog/PublicInfoPage";
import { BRAND_NAME } from "@/lib/brand";

export const metadata: Metadata = { title: `Chương trình | ${BRAND_NAME}`, description: "Các định hướng học tập ngoại ngữ theo mục tiêu." };
export default function Page() { return <ProgramsPage />; }
