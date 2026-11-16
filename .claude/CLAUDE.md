# Encore v2 application development

## Application model

Encore orchestrates infrastructure for ordinary application frameworks. Preserve
an existing application's framework, routes, dependency versions, and conventions.
Use the Infra SDK for resources; do not replace a framework app with the v1 API
framework or introduce v1 imports from old examples.

The app root contains `encore.app.json` (HuJSON: comments and trailing commas
allowed). Every service directory contains `encore.service.json` (strict JSON).
A service declares `name`, `lang`, its run strategy when needed, and its `api`.
The language values are `go`, `typescript`, `python`, and `rust`.
Bind the server to `ENCORE_LISTEN_ADDR` supplied by Encore. Do not hardcode a
port and assume the gateway will find it. Keep existing startup/shutdown handling.

Each `api` entry has a `type`. `expose` is `true` for the default gateway or a
list of gateway names. It decides what a gateway routes, not who may call: other
services, and locally the app port, reach unexposed endpoints too, so
authenticate in the handlers that need it.
- `{"type":"http","prefix":"/web","expose":true}` forwards everything at or
  below the prefix to the service, so no other service may expose a route under
  it (ENC0029); a `/` prefix owns the whole gateway. `name` defaults to the
  prefix's last segment and must be an identifier: set it for `/` or a segment
  with dashes or dots, e.g. `"name":"static_files"`.
- `{"type":"openapi","spec":"openapi.yaml"}`: every operation needs an
  `operationId`; expose with `x-encore: {expose: true}` on an operation, path
  item or the document root.
- `{"type":"grpc","protos":"proto"}` serves the gRPC services defined under that
  directory. Expose with `option (encore.expose) = true;` on a method
  (`encore.service_expose`, `encore.file_expose` for wider defaults) after
  `import "encore/annotations.proto";`.
- `{"type":"graphql","schema":"schema.graphql","expose":true}` mounts at `/graphql`.
Nothing can be exposed until a gateway is declared (ENC0028):
`{"name":"api","default":true}` in an `encore.gateway.json` in a directory of
its own (or a service's own), never in one above a service (ENC0020).
List the services a service calls in `"clients":["billing"]` to have typed
clients for them generated into its `encore_gen/`.

## Infrastructure and configuration

Declare resources at module/package scope with literal names and configuration
that Encore's static parser can discover. Import resource modules at startup.
Keep migrations in the configured directory, which is relative to the file that
declares the database and may not leave its directory, and use numbered SQL
migration files such as `1_create_users.up.sql`. Parameterize SQL; do not
interpolate user input.
Do not replace managed databases, buckets, or topics with process memory or files.
Use resource access references when passing resources to helpers, following the
installed SDK's API so Encore can infer permissions.

Pub/Sub is asynchronous and normally at-least-once. Make side effects idempotent
where required; do not assume delivery order without an ordered topic/key. Inspect
the language's message wrapper rather than treating it as the raw payload.
Validate untrusted inputs using the application's framework or explicit decoders;
type annotations alone do not validate incoming data.

Secret values belong in gitignored `secrets.user.toml` at the app root;
`encore secret set` reads a value from stdin. For a service's own secret, use
`encore secret set <service>.<Name>`; its TOML entry belongs in
`[services.<service>]`. Shared and global secrets use `[shared]`. Never commit
secret values.
Tests read placeholder values from the committed `secrets.test.toml` (same format)
before any other source; never put real credentials there.
Document what a secret is, who issues it and how to rotate it where it is
declared, with the SDK's `description` option or, except in Python, a doc
comment: it is shown wherever its values are managed.
Config values live in `<name>.config.toml` or `.json` beside the declaring
service manifest, or beside the app manifest for shared and global config.
Overlays are `<name>.<type>.config.toml` for an environment type (`local`,
`test`, `development`, `preview`, `production`) and `<name>.@<envname>.config.toml`
for one named environment; developer overrides use `<name>.user.config.toml`.
Use `encore config set` to change a value.
Do not edit generated `.encore/` or `encore_gen/` files.

## Verify changes

Run the app with `encore run`; this supplies runtime configuration and provisions
local resources. Locally one app port (4000 unless told otherwise) serves the
app by name: `http://localhost:4000/<name>/<path>` (or
`http://<name>.localhost:4000/<path>`) reaches a gateway, which serves exposed
routes only, or a service, any of its endpoints, exposed or not. `/` lists them.
The app port has no authentication: keep it on loopback, as it is by default.
Use `encore debug meta --format json` to inspect discovery.
`encore check` boots a fresh instance and accepts a request spec on stdin, e.g.:

    curl /health -fsS

Each line is a curl command with a URL relative to the default gateway. A
successful curl exit alone does not prove response correctness: check status,
body, and side effects.
Run application tests with `encore test` using the service's test strategy.
For a full restart, use `encore run new`: exiting `encore run` detaches and
leaves the session alive (`encore run stop` stops it). Local cron jobs are not
scheduled; run one with `encore cron trigger <name>` or call its POST handler.
Inspect emitted counters with `encore metrics get <service>.<metric> --since 5m`.
Use bounded polling for asynchronous effects, and test error paths and existing
routes as well as the new behavior. Report commands actually run and any blockers.

Use the APIs below for routine setup. For an unresolved signature or error,
search the installed package for that symbol and read its declaration/example;
avoid dumping whole SDK modules or surveying unrelated resources. Batch
independent lookups, then implement and verify. The installed SDK takes precedence
if its version differs from these examples. Use `<command> --help` for unfamiliar
CLI flags. Use MCP only if actually available
in the session; do not assume v1 tool names or an MCP configuration exists.
Encore records infrastructure telemetry through its own providers. To export app
and framework OpenTelemetry spans/metrics, install or pass Encore's providers;
do not assume the SDK replaces the process's OpenTelemetry globals.

## Go

Use the module `sdk.encore.dev` and the Go version declared in the app's go.mod.
Keep regular `net/http` or the application's chosen router. An ordinary Go
service can use `"run":{"type":"go"}` in its service manifest.

For ordinary telemetry, use `sdk.encore.dev/tracing`, `log/slog` and
`sdk.encore.dev/metrics` without OpenTelemetry setup:

    ctx, span := tracing.Start(ctx, "place_order")
    defer span.End()
    span.SetAttributes(tracing.String("order.id", id))

Pass that context to nested work and infrastructure calls. Record failures with
`Span.RecordError`; use slog context methods for trace/span IDs. Encore supplies
the default handler; use `env.NewLogHandler` for custom loggers. Wrap handlers per route:

    mux.Handle("POST /orders/{id}", tracing.HTTPHandler("/orders/{id}", handler))

The route is a fixed template, never a raw request path. An empty route is a
method-only fallback. The wrapper extracts W3C and Encore Request Context,
records status and 5xx errors, and records and rethrows panics. Mux-generated
redirects and method rejections before the wrapped handler are not traced.
Use http.ResponseController for optional writer operations; see
sdk/go/README.md for the fixed method-set contract and delegation details.
For advanced OTel libraries, pass `tracing.TracerProvider()`,
`tracing.Propagator()` and `metrics.MeterProvider()` explicitly, or explicitly
install globals. Native and OTel spans interoperate in either nesting direction;
use one server wrapper per handler. See `tests/go/telemetry/` for paired apps.

Declare Postgres with:

    import "sdk.encore.dev/storage/postgres"
    var db = postgres.NewDatabase("orders", postgres.DatabaseConfig{
        Migrations: "./migrations",
    })

Use `db.Exec(ctx, sql, args...)` and `db.QueryRow(ctx, sql, args...).Scan(...)`;
SQL parameters use `$1`, `$2`, etc. Propagate the request context and handle errors.
A missing row is `errors.Is(err, postgres.ErrNoRows)`. Transactions use
`tx, err := db.Begin(ctx)`, `defer tx.Rollback()` and `tx.Commit()`. Pass
helpers a `postgres.DatabaseRef` from `db.Read()` or `db.Write()`.
Declare object storage with `objects.NewBucket("uploads", objects.BucketConfig{})`
from `sdk.encore.dev/storage/objects`.
`uploads.Upload(ctx, key)` returns a writer: write bytes, check `Close()` to
finish, and `Abort(err)` on failure. Download with `uploads.Download(ctx, key)`,
read and close the reader; test missing objects with
`errors.Is(err, objects.ErrObjectNotFound)`.

Use `sdk.encore.dev/pubsub`: `NewTopic[T](name, TopicConfig{})` and
`NewSubscription(topic, name, SubscriptionConfig[T]{Handler: handler})`.
The handler takes `(context.Context, pubsub.Message[T])` and returns an error;
the payload is `msg.Data`. Publish with `topic.Publish(ctx, payload)` and check
the returned error. When ordering is required, use `NewOrderedTopic[T]` and
`topic.Publish(ctx, payload, orderingKey)`.

Import `encore "sdk.encore.dev"` and call `encore.Start()` in `main` once the
application is ready to handle messages, before serving HTTP. This starts the
registered Pub/Sub subscriptions; declaring them alone does not start delivery.
Ensure packages declaring handlers are imported. Databases and buckets initialize
on first use, so successful storage calls do not prove subscribers have started.

Common resource declarations and operations (imports under `sdk.encore.dev`):

| Resource / package | Package-scope declaration | Use |
|---|---|---|
| Redis / `storage/redis` | `var cache = redis.NewDatabase("cache", redis.DatabaseConfig{})` | `cache.String.Set(ctx, key, bytes)`; `cache.String.Get(ctx, key).Text()`; `cache.Generic.Del(ctx, key)` |
| Secret / `secrets` | `var key = secrets.New[string]("ApiKey")` | `key.Value()` returns the string; panics if the secret is not set |
| Config / `config` | `var settings = config.New[Settings]("settings")` | `settings.Get()`; use JSON field tags on `Settings` |
| Counter / `metrics` | `var requests = metrics.NewCounter[uint64]("requests_total")` | `requests.Increment(ctx)` |
| Cron / `cron` | `var cleanup = cron.NewJob("cleanup", cron.JobConfig{Path: "/internal/cleanup", Every: cron.Hour})` | Register `POST /internal/cleanup` on the router; run it with `encore cron trigger cleanup` |

Redis missing reads return `redis.ErrNil`; distinguish that from infrastructure
errors. Keep a cron route's literal path equal to `JobConfig.Path`: the parser
rejects reading `job.Path` (ENC0034). Config, secrets, and counters above belong
to their declaring service. `secrets.Config{Scope: secrets.Shared}` or
`config.Options{Scope: config.Shared}` makes one app-wide value that only the
services reading it get; `Global` makes it every service's. A config field is
required unless it is a pointer, `omitempty` or tagged `config:"optional"`; keys
match the json tag exactly.

Call another service through `sdk.encore.dev/services`, so the trace and Request
Context of `ctx` reach it: `var billing = services.NewClient("billing")`, then
`billing.Get(ctx, "/invoices")` (also Post, Put, Patch, Delete, Do). The name is
a string literal in a direct call of `NewClient` or `services.BaseURL` (ENC0038);
another http.Client uses `Transport: services.Transport(nil)`. A goroutine that
outlives the request takes `context.WithoutCancel(ctx)`, which keeps both. Under
`encore test`, outside system tests, service calls answer 501: mock them. A
service listing another in `"clients"` gets a package per API at
`<service dir>/encore_gen/clients/<service><api>`, imported by module path:

    user, err := catalogopenapi.GetUser(ctx, &catalogopenapi.GetUserInput{ID: 1},
        services.WithTimeout(time.Second))
    if services.Code(err) == services.NotFound { /* ... */ }

Request Context fields: `var tenant = reqctx.NewField[string]("tenant",
reqctx.FieldConfig{})`, read with `tenant.Get(r.Context())`, set with
`tenant.With(ctx, v)`.
Format changed files with gofmt; preserve graceful shutdown and close rows,
streams, and transactions.

## TypeScript

Install/use `@encore.dev/sdk`. Keep Express or the application's chosen HTTP
framework; use its validation and error handling. Respect the project's runtime,
package manager, lockfile, and scripts. A service on its own framework needs a
`run` strategy or nothing starts it: `"run":{"type":"script","script":"start"}`
runs that package.json script with the project's package manager;
`"run":{"type":"custom","cmd":["bun","run","start"]}` runs a command as given.

Declare Postgres with:

    import { Database } from "@encore.dev/sdk/storage/postgres";
    const db = new Database("orders", { migrations: "./migrations" });

Queries use tagged templates, for example:

    await db.queryRow`SELECT name FROM users WHERE id = ${id}`;
    await db.exec`INSERT INTO users (name) VALUES (${name})`;

These bind values; do not build SQL strings from request input. `queryRow`
returns `null` for no row, `queryAll` an array. Use
`await using tx = await db.begin()` and explicitly commit successful
transactions; disposal rolls back an uncommitted one. Failures throw
`DatabaseError` (`err.code === ErrorCode.UniqueViolation`).

Query type arguments describe results; they do not convert runtime values.
Postgres BYTEA values arrive as `ArrayBuffer`. Use `Buffer.from(value)` before
calling Buffer text-decoding methods or passing bytes to APIs requiring a Buffer.

Use `Bucket` from `@encore.dev/sdk/storage/objects` for storage.
Use `Topic`, `OrderedTopic`, and `Subscription` from `@encore.dev/sdk/pubsub`:

    const events = new Topic<{ id: string }>("events");
    const consumer = new Subscription(events, "process", {
      handler: async message => { console.log(message.data.id); },
    });

Declared subscriptions start automatically. `message.data` is decoded JSON by
default; `rawData` contains bytes. Use a `decode` callback for runtime validation,
or `encoding: "raw"` for byte payloads. `OrderedTopic.publish(msg, key)` requires
an explicit non-empty ordering key. Await publishing and other async calls.
Write resource options as `key: value` (`decode: data => ...`); the parser
rejects shorthand (`{ handler }`) and methods such as `decode(data) { ... }`.

Common declarations (module-scope; import paths below are under `@encore.dev/sdk`):

| Export / path | Declaration | Use |
|---|---|---|
| `Database as RedisDatabase` / `storage/redis` | `const cache = new RedisDatabase("cache")` | Command groups below |
| `secret` / `config` | `const apiKey = secret("ApiKey")` | `apiKey()` returns the string; throws if unset |
| `config` / `config` | `const settings = config<Settings>("settings")` | `settings()`; `Settings` is an interface/type |
| `Counter` / `metrics` | `const requests = new Counter("requests_total")` | `requests.increment()` is synchronous |
| `CronJob` / `cron` | `const cleanup = new CronJob("cleanup", {path: "/internal/cleanup", every: "1h"})` | Register `POST /internal/cleanup` on the framework |

Config, secrets, and counters above belong to their declaring service; pass
`{ scope: "shared" }` for one app-wide value that only the services using it
get, or `{ scope: "global" }` for one every service gets. Object storage
uses `await bucket.upload(key, buffer)` and `await bucket.download(key)`; catch
`ObjectNotFound` from `storage/objects` for missing reads. Typecheck and run the
project's existing tests.

Redis's `Database` exposes command groups: `await cache.string.set(key, value)`,
`await cache.string.get(key).text()` (string or null), and
`await cache.generic.del(key)`. Use the installed SDK's command groups and reply
conversions; do not assume the surface of another Redis client.

Call other services through `@encore.dev/sdk/services`, not a plain `fetch`, so
trace and Request Context propagate. `const billing = client("billing")` (a
string literal, called directly in a service: ENC0038), then
`await billing.fetch("/invoices")`. A service listed in `clients` gets typed
clients in the caller's `encore_gen/clients/`, a module per API entry:

    import { catalog } from "./encore_gen/clients/index.js";
    const user = await catalog.openapi.getUser(1);

A failed generated call throws `CallError` (`err.code === "not_found"`);
`unlessNotFound(call)` returns `undefined` instead. gRPC clients need
`@connectrpc/connect` and `@bufbuild/protobuf`.

Wrap the listener with `instrumentHTTP` so incoming trace and Request Context
reach handlers: `createServer(instrumentHTTP(app))` from `tracing/node`
(Express, `node:http`), or `tracing`'s for a fetch handler. Context then follows
`await`, timers and callbacks; `waitUntil(promise)` from `shutdown` holds
shutdown for detached work, and `onShutdown(() => ...)` drains the server. Log
with `log.info("msg", { key })` and `log.error(err, "msg")`
(`import log from "@encore.dev/sdk/log"`); `span(name, async current => ...)`
from `tracing` records a span. The SDK registers no OTel globals: pass
`tracerProvider()`/`meterProvider()` from `@encore.dev/sdk`.

## Python

The distribution is `encore-dev`; imports use `encore`. Keep FastAPI, Django,
Flask or the application's existing framework. Respect pyproject.toml and the
lockfile. The service manifest uses `"lang":"python"`. Without a `run` entry,
Encore runs `main.py` (else `app.py`) from the service directory through the
tool whose lockfile is there (`uv.lock` gives `uv run main.py`; poetry, pipenv,
pdm likewise; none gives `python3`).
`"run":{"type":"python","entry":"-m app.server"}` names another entry. With the
lockfile in a parent directory, use:

    "run": {"type": "custom", "cmd": ["uv", "run", "python", "main.py"]}

It also runs from the service directory; `run.command` is not a supported field.
Verify the actual HTTP response after startup; discovering a service does not
prove its Python imports succeed.

Declare resources at module scope, assigned to a variable:

    from encore.storage import postgres, objects
    db = postgres.Database("orders", migrations="./migrations")
    uploads = objects.Bucket("uploads")

Query with `await db.query("SELECT name FROM users WHERE id = $1", user_id).one()`
(`postgres.NoRowsError` on no row), `.first()` for an optional row, or `.all()`;
rows are dicts. Writes use `await db.exec(sql, *params)`; transactions use
`async with db.begin() as tx:`, committing on a clean exit. `postgres.DatabaseError`
has `.code`, e.g. `postgres.ErrorCode.UNIQUE_VIOLATION`. Query cursors are
single-consumption. Exhaust or close streams; use context managers for early
exits. Await `uploads.upload(name, data)` and `uploads.download(name)`; missing
objects raise `objects.ObjectNotFound`. Translate SDK errors to suitable HTTP
responses. Pass helpers `db.read()`/`db.write()` or
`uploads.ref(objects.Downloader)`.

Use `encore.pubsub.Topic`, `Subscription`, and `Message`. A payload is a JSON
value, bytes, or a Pydantic v2 model (validated on decode); other types such as
dataclasses raise TypeError at startup. Assign the subscription at module scope
and make sure its module is imported. Publish with `await events.publish(event)`:

    events = pubsub.Topic[Event]("events")
    async def handle_event(message: pubsub.Message[Event]) -> None: ...
    process = pubsub.Subscription[Event](events, "process", handler=handle_event)

Serve an ASGI app (FastAPI, Starlette) with `encore.run(app)` under
`if __name__ == "__main__":`; Flask as `encore.run(a2wsgi.WSGIMiddleware(app))`;
a service without HTTP calls `encore.run()`. It binds `ENCORE_LISTEN_ADDR`, runs
the lifespan, starts subscriptions, traces requests and drains on shutdown.
An app that keeps its own server calls `await encore.start()` from its async
startup hook (FastAPI: lifespan before `yield`) after importing resource
modules; importing the SDK starts no consumers, and an `asyncio.run()` loop that
closes before the server runs stops them. On shutdown, while that loop still
runs, call `encore.shutdown.begin()` and await `encore.shutdown.completed()`
(FastAPI: in a `finally` after `yield`), keeping the app's other cleanup.

Importing the SDK initializes its native runtime synchronously. Launch through
Encore so configuration exists before imports, and use `encore test` for tests
that import app resources. Initialize independently in each worker process;
do not fork an already initialized native runtime.

Common resource declarations and operations (at module scope):

| Import | Declaration | Use |
|---|---|---|
| `from encore.storage import redis` | `cache = redis.Database("cache")` | `await cache.string.set(key, data)`; `await cache.string.get(key)` returns bytes or None; `await cache.generic.delete(key)` |
| `from encore.secrets import Secret` | `api_key = Secret[str]("ApiKey")` | `api_key.value` is a str (KeyError if unset); the constructor needs `[str]`. `scope="shared"` makes one app-wide value only the services reading it get, `scope="global"` one every service gets; another service binds a shared one with `Secret[str].named("ApiKey")` |
| `from encore.config import Config` | `settings = Config[Settings]("settings")` | `settings.value`; `Settings` can be a dataclass |
| `from encore.metrics import Counter` | `requests = Counter("requests_total")` | `requests.increment()` is synchronous |
| `from encore.cron import Job` | `cleanup = Job("cleanup", path="/internal/cleanup", every="1h")` | Register `POST /internal/cleanup` on the framework |

Config, secrets, and counters above belong to their declaring service. Call
another service with an `encore.services` adapter (`httpx`, `requests`,
`aiohttp`, `niquests`; install e.g. `encore-dev[httpx]`), not a plain client,
so trace and Request Context propagate. Pass the name as a string literal (ENC0038):

    from encore.services import httpx as services
    billing = services.client("billing")
    response = await billing.get("/invoices")

For each service in `clients`, Encore generates `encore_gen/clients/<service>/`
beside the manifest, a module per API with async functions:
`from encore_gen.clients import catalog`, `await catalog.openapi.get_product("x")`.
Failures raise `encore.services.CallError` with `.code` (`encore.errs.ErrCode`).
Under `encore test` no service runs and calls answer 501; mock them. asyncio
tasks and `asyncio.to_thread` carry the trace and Request Context; a
`threading.Thread` or executor needs `contextvars.copy_context().run(fn)`.
Use the project's lint, typecheck, and test tools. Keep blocking work off async
request handlers; use `encore.logs.StructuredLogHandler` with standard logging when
integrating application logs.

## Rust

The Cargo package is `encore-dev`; the Rust crate is `encore`. Keep Axum or the
application's existing HTTP framework. The service manifest uses `"lang":"rust"`
and can use `"run":{"type":"rust"}`. Respect Cargo.toml and Cargo.lock.

Initialize the SDK with `encore::initialize()` during startup before using
resources. Declare resources as statics:

    use encore::storage::postgres::Database;
    use encore::objects::Bucket;
    static DB: Database = Database::new("orders").migrations("./migrations");
    static UPLOADS: Bucket = Bucket::new("uploads");

`new` declares a resource; `Database::named("orders")` (likewise `Bucket`,
`Topic`) uses one that another service declares. A database declared in
`src/main.rs` keeps its migrations in `src/migrations`.
Postgres and bucket errors (`postgres::Error`, `objects::Error`) do not convert
into `encore::Error`, so a bare `?` does not compile where one is returned.
Map them with the code that fits:

    let row = DB
        .query_opt("SELECT name FROM users WHERE id = $1", &[&id])
        .await
        .map_err(|e| encore::Error::internal(e.to_string()))?;
    let name: Option<String> = row.map(|row| row.get("name"));

`query_one` wants exactly one row (else `postgres::Error::NoRows`); `query`
returns all rows. `row.get(..)` panics on a type mismatch, `row.try_get(..)`
returns a `postgres::Error`. Writes use `DB.execute(sql, &[&value])`;
transactions use `let tx = DB.transaction().await`, the same query methods on
`tx`, and `tx.commit().await`, each mapped as above. Objects use
`UPLOADS.upload(key, bytes_vec).await` and `UPLOADS.download(key).await` (a
`Vec<u8>`); a missing object is `Err(encore::objects::Error::NotFound)`.
Propagate errors and translate them into HTTP responses; avoid panicking on input.

Use `encore::pubsub::{Topic, Subscription, Message}` for events. Declare topics
and subscriptions as statics; put `#[encore::pubsub::register]` on subscriptions
so `encore::initialize()` starts them.
For `Topic<Event>`, use `Topic::new("events")` and
`Subscription::new(&EVENTS, "process", handler)`. The handler is
`async fn handler(msg: Message<Event>) -> Result<(), encore::Error>` and reads
`msg.data`. Without the attribute, pass `|msg| Box::pin(handler(msg))` and call
the subscription's `start()`. Derive `Serialize, Deserialize` on `Event`;
publish with `EVENTS.publish(&event).await?`. Make side effects idempotent as
required.

Common declarations (module-scope statics; paths under `encore`):

| Resource | Declaration | Use |
|---|---|---|
| Redis | `static CACHE: storage::redis::Database = storage::redis::Database::new("cache");` | `CACHE.string().set(key, bytes).await?`; `CACHE.string().get::<Option<String>>(key).await?`; `CACHE.generic().del(key).await?` (errors are `encore::Error`) |
| Secret | `static KEY: secrets::Secret = secrets::Secret::new("ApiKey");` | `KEY.value()` returns a `Value` that derefs to `String`; it panics if the secret has no value |
| Config | `static SETTINGS: config::Config<Settings> = config::Config::new("settings");` | `SETTINGS.get()` is a snapshot that derefs to `Settings`; derive `serde::Deserialize, config::ConfigType` on `Settings` |
| Counter | `static REQUESTS: metrics::Counter = metrics::Counter::new("requests_total");` | `REQUESTS.increment()` |
| Cron | `static CLEANUP: cron::Job = cron::Job::new("cleanup", "/internal/cleanup", cron::Schedule::Every("1h"));` | Register a POST route at `CLEANUP.path()` |

Configs, secrets and metrics belong to their declaring service. Chain
`.shared()` onto `new(..)` for one app-wide value that only the services using
it get, or `.global()` for one every service gets.

Call another service with `encore::services`, not a plain HTTP client, so the
trace and Request Context propagate. The name must be a string literal in a
direct call (ENC0038):

    static BILLING: encore::services::Client = encore::services::client("billing");
    let resp = BILLING.get("/invoices").send().await; // reqwest::Result<Response>

With `"clients":["billing"]`, declare `mod encore_gen;` at the crate root and
call `encore_gen::clients::billing::<entry>::<operation>(..).await?` (e.g.
`billing::openapi::get_invoice(id)`); its error converts into `encore::Error`
with the same code. A spawned task starts without the trace and Request
Context: spawn `fut.with_current_context()`
(`encore::opentelemetry::trace::FutureExt`).

Choose one logging path; the application owns its globals:
- Tracing: compose `encore::telemetry::tracing::layer()` with `SubscriberExt`, install the
  subscriber explicitly, emit structured events and use `tracing::Instrument`
  for futures. Optionally install `tracing_log::LogTracer::init()` once at app startup
  to forward standard `log` records. Entered spans activate resource context.
- Log only: call `encore::log::set_logger(encore::telemetry::log::logger())?` and
  `encore::log::set_max_level(...)`. `encore::log` is the standard facade; the
  direct console adapter preserves typed KV and native OTel context without a
  subscriber. Internal tracing diagnostics are excluded; native infrastructure
  spans and metrics remain independent. Logger queries do not initialize the
  runtime. Standalone console users call `encore::telemetry::log::flush()`.
Pass `encore::telemetry::tracer_provider()` and
`encore::metrics::meter_provider()` explicitly to OTel instrumentation. Native
OTel futures use `.with_context(cx)` per poll. Preserve graceful shutdown with
`encore::shutdown::signal()` and `drained()`. Run cargo fmt, cargo check, and
relevant tests with the runtime available where required.
