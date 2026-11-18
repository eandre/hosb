module hosb/web

go 1.27.4

// The Vite app's packages, some of which carry Go code of their own.
ignore ./node_modules

// Encore provides its SDK to the build, through a Go workspace of its own.
require sdk.encore.dev v0.0.0

require (
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/go-logr/logr v1.4.4 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	go.opentelemetry.io/auto/sdk v1.2.1 // indirect
	go.opentelemetry.io/otel v1.46.0 // indirect
	go.opentelemetry.io/otel/metric v1.46.0 // indirect
	go.opentelemetry.io/otel/trace v1.46.0 // indirect
)
