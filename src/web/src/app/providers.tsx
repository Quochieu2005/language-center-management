"use client";

import { ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import type { ReactNode } from "react";

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
          colorError: "#1D2926",
          colorWarning: "#1D2926",
          colorText: "#1D2926",
          colorBgBase: "#F6F5F0",
          colorBorder: "rgba(29, 41, 38, 0.18)",
          fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          borderRadius: 10,
          controlHeight: 44,
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}
