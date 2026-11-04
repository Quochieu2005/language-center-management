import FinalCTASection from "@/components/web/home/sections/FinalCTASection/FinalCTASection";
import ContactGuide from "@/components/web/contact/ContactGuide";
import WebPageLayout from "@/components/web/layout/WebPageLayout";

export default function ContactPage() {
  return (
    <WebPageLayout>
      <FinalCTASection variant="contact" />
      <ContactGuide />
    </WebPageLayout>
  );
}
