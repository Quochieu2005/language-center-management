import type { Metadata } from "next";
import { ContactPage } from "@/components/web/catalog/PublicInfoPage";
import { BRAND_NAME } from "@/lib/brand";

export const metadata: Metadata = { title: `Liên hệ | ${BRAND_NAME}`, description: "Thông tin liên hệ và trạng thái tư vấn." };
export default function Page() { return <ContactPage />; }
