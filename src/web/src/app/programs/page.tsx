import type { Metadata } from "next";
import { ProgramsPage } from "@/components/web/catalog/PublicInfoPage";

export const metadata: Metadata = { title: "Chương trình | [Tên trung tâm]", description: "Các định hướng học tập ngoại ngữ theo mục tiêu." };
export default function Page() { return <ProgramsPage />; }
