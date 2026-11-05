import type { Metadata } from "next";
import { ContactPage } from "@/components/web/catalog/PublicInfoPage";

export const metadata: Metadata = { title: "Liên hệ | [Tên trung tâm]", description: "Thông tin liên hệ và trạng thái tư vấn." };
export default function Page() { return <ContactPage />; }
