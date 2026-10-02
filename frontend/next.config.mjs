/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.DATAID_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // keeps the browser on one origin, so SSE and cookies work without CORS juggling
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
