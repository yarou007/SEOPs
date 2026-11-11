import type { NextConfig } from "next";

const backend = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);
const config: NextConfig = {
  poweredByHeader: false,
  // AI insight requests can take up to ~3 minutes; the default proxy timeout is 30 s.
  experimental: { proxyTimeout: 180_000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
export default config;
