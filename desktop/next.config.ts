import type { NextConfig } from "next";

// static export: tauri serves the out/ directory, no node server at runtime
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
