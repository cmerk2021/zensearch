/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    const backend = process.env.ZEN_BACKEND_URL || "http://localhost:8000";
    return [
      { source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` },
      { source: "/metrics", destination: `${backend}/metrics` },
    ];
  },
};

module.exports = nextConfig;
