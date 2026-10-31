"use client";

import React from "react";
import styles from "./HomePage.module.scss";
import WebHeader from "@/components/web/layout/WebHeader";
import WebFooter from "@/components/web/layout/WebFooter";
import HeroSection from "./sections/HeroSection/HeroSection";
import ProofSection from "./sections/ProofSection/ProofSection";
import CoursePreviewSection from "./sections/CoursePreviewSection/CoursePreviewSection";
import BranchesSection from "./sections/BranchesSection/BranchesSection";
import BenefitsSection from "./sections/BenefitsSection/BenefitsSection";
import FAQSection from "./sections/FAQSection/FAQSection";
import FinalCTASection from "./sections/FinalCTASection/FinalCTASection";

export default function HomePage() {
  return (
    <div className={styles.homeContainer}>
      {/* PWS Solutions Style Web Header */}
      <WebHeader />

      {/* Main Sections */}
      <main className={styles.mainContent}>
        {/* 1. Hero & Course Finder */}
        <HeroSection />

        {/* 2. Real Stats & Metrics */}
        <ProofSection />

        {/* 3. Core Courses */}
        <CoursePreviewSection />

        {/* 4. 3 Campuses Network */}
        <BranchesSection />

        {/* 5. Distributed Architecture Benefits */}
        <BenefitsSection />

        {/* 6. FAQ Accordion */}
        <FAQSection />

        {/* 7. Final Interactive Consultation CTA */}
        <FinalCTASection />
      </main>

      {/* PWS Solutions Style Web Footer */}
      <WebFooter />
    </div>
  );
}
