// Command web serves the members' calendar, behind the api gateway: the Vite
// app in src/, built into dist/app before the program is (the build's
// prebuild hook) and embedded in it, and the app's API, /api/*, which it
// passes on to the community service. The page calls the API on its own
// origin.
package main

import (
	"embed"
	"errors"
	"io/fs"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"path"
	"strings"
	"time"

	encore "sdk.encore.dev"
	"sdk.encore.dev/services"
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
	community, err := url.Parse(services.BaseURL("community"))
	if err != nil {
		panic(err)
	}
	previews := fetchPreviews(&http.Client{Transport: services.Transport(nil)}, community)
	h := handler(
		tracing.HTTPHandler("/{path...}", newSite(built, previews)),
		tracing.HTTPHandler("/api/{path...}", apiProxy(community, services.Transport(nil))),
	)

	encore.Start()
	srv := &http.Server{
		Addr:              os.Getenv("ENCORE_LISTEN_ADDR"),
		Handler:           h,
		ReadHeaderTimeout: 10 * time.Second,
	}
	// Finish the requests in flight before Encore stops the service.
	shutdown.OnShutdown(srv.Shutdown)
	slog.Info("serving the app", "addr", srv.Addr)
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		slog.Error("serving failed", "err", err)
	}
}

// handler sends /api and what's below it to api, and the rest to app. The
// path is judged as it reads once cleaned, which is as it's passed on.
func handler(app, api http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		clean := path.Clean("/" + r.URL.Path)
		if clean == "/api" || strings.HasPrefix(clean, "/api/") {
			r.URL.Path, r.URL.RawPath = clean, ""
			api.ServeHTTP(w, r)
			return
		}
		app.ServeHTTP(w, r)
	})
}

// apiProxy passes requests on to the community service as they came, path
// and all, and its answers back as they went: redirects too, as Google's
// sign-in callback answers with one. Encore's transport (services.Transport)
// carries the request's trace on, and signs the call as the service's.
func apiProxy(community *url.URL, transport http.RoundTripper) *httputil.ReverseProxy {
	return &httputil.ReverseProxy{
		Rewrite: func(r *httputil.ProxyRequest) {
			r.SetURL(community)
			r.SetXForwarded()
		},
		Transport: transport,
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			slog.ErrorContext(r.Context(), "the API could not be reached", "err", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_, _ = w.Write([]byte(`{"detail":"the API could not be reached"}`))
		},
	}
}
