/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produces a minimal standalone server bundle — smaller image for the Raspberry Pi.
  output: "standalone",
};

export default nextConfig;
