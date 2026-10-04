import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8080";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/frame", destination: `${BACKEND}/frame` },
      { source: "/parse", destination: `${BACKEND}/parse` },
      { source: "/suggest", destination: `${BACKEND}/suggest` },
      { source: "/edit", destination: `${BACKEND}/edit` },
    ];
  },
};

export default nextConfig;
