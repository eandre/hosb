/** @type {import("next").NextConfig} */
const config = {
  // A release of only the files Next.js's server loads, traced from this
  // app (scripts/release.mjs packages it with server.mjs).
  output: "standalone",
  outputFileTracingRoot: import.meta.dirname,
  // Where the build goes: server.mjs points a test session's dev server
  // elsewhere, as it runs as long as `encore run`'s, beside it.
  distDir: process.env.WEB_NEXT_DIST_DIR || ".next",
  experimental: {
    // Next.js runs one dev server per build directory, and refuses a second.
    // Encore starts a rebuilt service beside the one serving, and stops the
    // old one once the new one is up, so for that moment there are two.
    lockDistDir: false,
  },
  poweredByHeader: false,
}

export default config
