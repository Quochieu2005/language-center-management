import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import type { ReactNode } from "react";
import AppProviders from "./providers";
import "./globals.css";
import "@/styles/globals.scss";
import { BRAND_NAME } from "@/lib/brand";

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: "Giao diện hệ thống quản lý trung tâm đào tạo ngoại ngữ.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" data-scroll-behavior="smooth">
      <body>
        <AntdRegistry>
          <AppProviders>{children}</AppProviders>
        </AntdRegistry>
      </body>
    </html>
  );
}
