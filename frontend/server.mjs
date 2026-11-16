// Serves the Next.js app where Encore assigns the service, ENCORE_LISTEN_ADDR,
// and the API beside it at /api, passed on to the community service: the
// browser talks to one origin. Each request is traced, and the API calls
// continue its trace.
//
//   node server.mjs --dev   the dev server, with hot reload (`encore run`)
//   node server.mjs         the built app (`bun run build` first)
//
// Encore's SDK is used here, outside Next.js's bundles, which it loads its
// native runtime around.

import { createServer } from "node:http"
import { Readable } from "node:stream"
import { appMeta } from "@encore.dev/sdk"
import { client } from "@encore.dev/sdk/services"
import { onShutdown } from "@encore.dev/sdk/shutdown"
import { instrumentHTTP } from "@encore.dev/sdk/tracing/node"
import next from "next"

const dev = process.argv.includes("--dev")
const community = client("community")

// A test session's dev server builds apart from `encore run`'s, which Next.js
// would otherwise refuse to run beside (see next.config.mjs).
if (dev && appMeta().environment.type === "test") {
  process.env.WEB_NEXT_DIST_DIR = ".next-test"
}

/** "127.0.0.1:4100", ":8080" or "[::]:8080" as a host and a port. */
function parseAddr(addr) {
  const i = addr.lastIndexOf(":")
  const host = addr.slice(0, i).replace(/^\[(.*)\]$/, "$1")
  return { hostname: host || "0.0.0.0", port: Number(addr.slice(i + 1)) }
}

// Hop-by-hop headers, and those fetch sets itself.
const DROP_REQUEST = new Set(["host", "connection", "keep-alive", "transfer-encoding", "upgrade", "content-length"])
// fetch has decoded the body, so its encoding and length no longer hold.
const DROP_RESPONSE = new Set(["connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"])

/** Passes an /api request on to the community service as it came, and its
 * answer back as it went, redirects included (Google's OAuth callback
 * answers with one). */
async function proxyAPI(req, res) {
  const headers = new Headers()
  for (const [key, value] of Object.entries(req.headers)) {
    if (DROP_REQUEST.has(key) || value === undefined) continue
    for (const v of Array.isArray(value) ? value : [value]) headers.append(key, v)
  }
  const hasBody = req.method !== "GET" && req.method !== "HEAD"
  let answer
  try {
    answer = await community.fetch(req.url, {
      method: req.method,
      headers,
      body: hasBody ? Readable.toWeb(req) : undefined,
      duplex: hasBody ? "half" : undefined,
      redirect: "manual",
    })
  } catch (err) {
    console.error("web: the API could not be reached", err)
    res.writeHead(502, { "content-type": "application/json" })
    res.end(JSON.stringify({ detail: "the API could not be reached" }))
    return
  }
  const out = {}
  answer.headers.forEach((value, key) => {
    if (!DROP_RESPONSE.has(key)) out[key] = key in out ? [].concat(out[key], value) : value
  })
  const cookies = answer.headers.getSetCookie?.() ?? []
  if (cookies.length) out["set-cookie"] = cookies
  res.writeHead(answer.status, answer.statusText, out)
  if (answer.body) {
    Readable.fromWeb(answer.body).pipe(res)
  } else {
    res.end()
  }
}

const { hostname, port } = parseAddr(
  process.env.ENCORE_LISTEN_ADDR ?? `127.0.0.1:${process.env.PORT ?? 3000}`,
)
const app = next({ dev, dir: import.meta.dirname, hostname, port })
const handle = app.getRequestHandler()
await app.prepare()

const server = createServer(
  instrumentHTTP((req, res) => {
    if (req.url === "/api" || req.url?.startsWith("/api/") || req.url?.startsWith("/api?")) {
      return proxyAPI(req, res)
    }
    return handle(req, res)
  }),
)
server.listen(port, hostname, () => {
  console.log(`web: serving ${dev ? "the dev server" : "the built app"} on http://${hostname}:${port}`)
})

// Finish the requests in flight before Encore stops the service.
onShutdown(() => new Promise((resolve) => server.close(() => resolve())))
