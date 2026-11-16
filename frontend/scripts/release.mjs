// Packages the built app as the service's release, after `next build`, when
// Encore builds the service: it runs the package's build script with
// ENCORE_OUTPUT_DIR set, and the image holds what is written there, and
// nothing else. Run without it, as a plain `bun run build`, it does nothing.
//
// The release is the build (.next, without its caches), the static files,
// the server, and the production dependencies, installed for the release,
// without the optional ones: Next.js's compiler and image tools, which
// serving a built app doesn't use.

import { execFileSync } from "node:child_process"
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { isAbsolute, join, resolve } from "node:path"

const root = resolve(import.meta.dirname, "..")
const out = process.env.ENCORE_OUTPUT_DIR
if (!out) {
  console.log("release: not an Encore build (no ENCORE_OUTPUT_DIR): nothing to package")
  process.exit(0)
}
mkdirSync(out, { recursive: true })

cpSync(join(root, ".next"), join(out, ".next"), {
  recursive: true,
  // The build caches and a dev server's output are no part of a release.
  filter: (src) => !/[/\\]\.next[/\\](cache|dev)([/\\]|$)/.test(src),
})
for (const file of ["public", "server.mjs", "next.config.mjs"]) {
  if (existsSync(join(root, file))) cpSync(join(root, file), join(out, file), { recursive: true })
}

// A local `file:` dependency is relative to this directory: make it absolute,
// in the manifest and the lockfile alike, so that it installs from the
// release's, at the versions locked.
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"))
let lock = readFileSync(join(root, "bun.lock"), "utf8")
for (const deps of [pkg.dependencies, pkg.devDependencies]) {
  for (const [name, spec] of Object.entries(deps ?? {})) {
    if (spec.startsWith("file:") && !isAbsolute(spec.slice(5))) {
      deps[name] = `file:${resolve(root, spec.slice(5))}`
      lock = lock.replaceAll(spec, deps[name])
    }
  }
}
writeFileSync(join(out, "package.json"), JSON.stringify(pkg, null, 2))
writeFileSync(join(out, "bun.lock"), lock)

console.log("release: installing the production dependencies")
execFileSync("bun", ["install", "--production", "--omit", "optional"], { cwd: out, stdio: "inherit" })
console.log(`release: packaged into ${out}`)
