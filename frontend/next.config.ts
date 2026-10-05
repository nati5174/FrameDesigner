import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8080";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/health", destination: `${BACKEND}/health` },
      { source: "/frame", destination: `${BACKEND}/frame` },
      { source: "/parse", destination: `${BACKEND}/parse` },
      { source: "/suggest", destination: `${BACKEND}/suggest` },
      { source: "/edit", destination: `${BACKEND}/edit` },
      { source: "/cut-plan", destination: `${BACKEND}/cut-plan` },
      { source: "/export/step", destination: `${BACKEND}/export/step` },
    ];
  },
};

export default nextConfig;
