import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import type { ReactNode } from "react";
import AppProviders from "./providers";
import "./globals.css";
import "@/styles/globals.scss";

export const metadata: Metadata = {
  title: "Quản lý trung tâm đào tạo ngoại ngữ",
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
