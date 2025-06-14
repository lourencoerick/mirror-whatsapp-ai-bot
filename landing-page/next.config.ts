import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
   /**
   * Defines server-side redirects.
   * This is the recommended way to handle permanent URL changes for SEO and user experience.
   * @returns {Promise<Array<object>>} A promise that resolves to an array of redirect rules.
   */
  async redirects() {
    return [
      {
        // The old URL path that we want to redirect FROM.
        source: '/beta-signup',
        // The new URL path that we want to redirect TO.
        destination: '/beta',
        // This is crucial. `true` sets the HTTP status code to 301 (Permanent Redirect).
        permanent: true,
      },
      // You can add more redirect rules here in the future.
    ];
  },
};

export default nextConfig;
