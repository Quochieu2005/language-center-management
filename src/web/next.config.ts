import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep Cache Components disabled: Ant Design's SSR style registry creates
  // runtime IDs while rendering, which the prerender cache rejects.
};

export default nextConfig;
