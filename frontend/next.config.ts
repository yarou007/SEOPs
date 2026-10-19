import type { NextConfig } from "next";

const backend = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);
const config: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
export default config;
