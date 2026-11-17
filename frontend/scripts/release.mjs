// Packages the built app as the service's release, after `next build`, when
// Encore builds the service: it runs the package's build script with
// ENCORE_OUTPUT_DIR set, and the image holds what is written there, and
// nothing else. Run without it, as a plain `bun run build`, it does nothing.
//
// The release is Next.js's standalone output (next.config.mjs): the files
// its server loads, traced from the app, with the static files it serves,
// which the standalone output leaves out. Beside them goes server.mjs, which
// Next.js doesn't trace, with the packages it loads itself: Encore's SDK and
// the SDK's dependencies. Encore's build then puts the SDK's native runtime
// into the release's copy of it.

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs"
import { join, resolve } from "node:path"

const root = resolve(import.meta.dirname, "..")
const out = process.env.ENCORE_OUTPUT_DIR
if (!out) {
  console.log("release: not an Encore build (no ENCORE_OUTPUT_DIR): nothing to package")
  process.exit(0)
}

const standalone = join(root, ".next", "standalone")
if (!existsSync(join(standalone, "server.js"))) {
  throw new Error(`release: ${standalone} has no server.js: is next.config.mjs's output "standalone"?`)
}
mkdirSync(out, { recursive: true })

// Copies as real files: the SDK installed from a checkout of Encore is
// links into it, which would lead nowhere in the image.
const copy = (from, to, filter) => cpSync(from, to, { recursive: true, dereference: true, filter })

// The traced server, its .next and node_modules. Its own server.js is
// server.mjs's to replace, and the build's caches are no part of a release.
copy(standalone, out, (src) => !/[/\\]\.next[/\\]cache([/\\]|$)/.test(src))
rmSync(join(out, "server.js"))
copy(join(root, ".next", "static"), join(out, ".next", "static"))
if (existsSync(join(root, "public"))) copy(join(root, "public"), join(out, "public"))
copy(join(root, "server.mjs"), join(out, "server.mjs"))
copy(join(root, "next.config.mjs"), join(out, "next.config.mjs"))

// The packages server.mjs loads that the standalone output lacks, with their
// own required dependencies and peers. Only what a package publishes: its
// manifest and its files, not its own node_modules, and no native module,
// which Encore's build puts in for the image's platform.
const want = ["@encore.dev/sdk"]
const done = new Set()
while (want.length) {
  const name = want.pop()
  if (done.has(name)) continue
  done.add(name)
  const dir = join(root, "node_modules", name)
  if (!existsSync(join(dir, "package.json"))) {
    throw new Error(`release: ${name}, which server.mjs needs, is not installed in ${dir}`)
  }
  const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"))
  const dest = join(out, "node_modules", name)
  rmSync(dest, { recursive: true, force: true })
  copy(dir, dest, (src) => {
    const rel = src.slice(dir.length)
    return !/^[/\\](node_modules|\.git)([/\\]|$)/.test(rel) && !src.endsWith(".node")
  })
  const optional = pkg.peerDependenciesMeta ?? {}
  for (const dep of Object.keys(pkg.dependencies ?? {})) want.push(dep)
  for (const dep of Object.keys(pkg.peerDependencies ?? {})) {
    if (!optional[dep]?.optional) want.push(dep)
  }
}

console.log(`release: packaged into ${out}, with ${[...done].join(", ")}`)
