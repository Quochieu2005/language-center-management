"use client";

import { ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import type { ReactNode } from "react";
import { SessionProvider } from "@/lib/auth/session";

type AppProvidersProps = {
  children: ReactNode;
};

export default function AppProviders({ children }: AppProvidersProps) {
  return (
    <ConfigProvider
      locale={viVN}
      theme={{
        token: {
          colorPrimary: "#2C746B",
          colorInfo: "#2C746B",
          colorSuccess: "#2C746B",
          fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          borderRadius: 10,
          controlHeight: 44,
        },
      }}
    >
      <SessionProvider>{children}</SessionProvider>
    </ConfigProvider>
  );
}
