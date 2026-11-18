// Command web serves the members' calendar on the webgw gateway: the Vite app
// in src/, built into dist/app before the program is (the build's prebuild
// hook), and embedded in it. The app's page is told the URL of the api
// gateway, where the community service's API is exposed, and calls it there.
package main

import (
	"embed"
	"errors"
	"io/fs"
	"log/slog"
	"net/http"
	"os"
	"time"

	encore "sdk.encore.dev"
	"sdk.encore.dev/gateways"
	"sdk.encore.dev/shutdown"
	"sdk.encore.dev/tracing"
)

// The app, once built (bun run build): dist/ holds only a README until then.
//
//go:embed all:dist
var dist embed.FS

func main() {
	defer shutdown.Exit()

	built, err := fs.Sub(dist, "dist/app")
	if err != nil {
		panic(err)
	}
	app, err := newSite(built, gateways.URL("api"))
	if err != nil {
		slog.Error("the app can't be served", "err", err)
		return
	}

	mux := http.NewServeMux()
	mux.Handle("GET /{path...}", tracing.HTTPHandler("/{path...}", app))

	encore.Start()
	srv := &http.Server{
		Addr:              os.Getenv("ENCORE_LISTEN_ADDR"),
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}
	// Finish the requests in flight before Encore stops the service.
	shutdown.OnShutdown(srv.Shutdown)
	slog.Info("serving the app", "addr", srv.Addr)
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		slog.Error("serving failed", "err", err)
	}
}
