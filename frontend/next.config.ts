import type { NextConfig } from "next";

const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  agentRules: false,
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backendOrigin}/api/v1/:path*` }];
  },
  async headers() {
    return [{ source: "/api/v1/:path*", headers: [{ key: "Cache-Control", value: "no-store" }] }];
  },
};

export default config;
