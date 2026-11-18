package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"path"
	"strings"
)

// site serves a single-page app's built files: each file as it is, and the
// app's page, index.html, for every other path, the app's own routes. The
// page is told where the API is.
type site struct {
	files fs.FS
	// The app's page, with the script that tells it where the API is; nil if
	// the app hasn't been built.
	page   []byte
	static http.Handler
}

// pageConfig is what the page is told, as window.hosb (src/vite-env.d.ts).
type pageConfig struct {
	// The URL of the gateway the API is exposed on.
	APIURL string `json:"apiURL"`
}

// newSite serves the app built into files, telling it the API is at apiURL.
func newSite(files fs.FS, apiURL string) (*site, error) {
	s := &site{files: files, static: http.FileServerFS(files)}
	page, err := fs.ReadFile(files, "index.html")
	if err != nil {
		// Unbuilt: every request says so, rather than the program not starting.
		return s, nil
	}
	config, err := json.Marshal(pageConfig{APIURL: apiURL})
	if err != nil {
		return nil, err
	}
	// Marshal escapes <, > and &, so the value can't end the script early.
	script := fmt.Sprintf("<script>window.hosb = %s</script>\n  </head>", config)
	if !bytes.Contains(page, []byte("</head>")) {
		return nil, fmt.Errorf("index.html has no </head> to put the page's config before")
	}
	s.page = bytes.Replace(page, []byte("</head>"), []byte(script), 1)
	return s, nil
}

func (s *site) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if s.page == nil {
		http.Error(w, "The app hasn't been built: run `bun run build` in frontend/.", http.StatusServiceUnavailable)
		return
	}
	h := w.Header()
	h.Set("X-Content-Type-Options", "nosniff")

	name := strings.TrimPrefix(path.Clean("/"+r.URL.Path), "/")
	if name != "" && name != "index.html" {
		if info, err := fs.Stat(s.files, name); err == nil && !info.IsDir() {
			// Vite names what's in assets/ by its contents: it never changes.
			if strings.HasPrefix(name, "assets/") {
				h.Set("Cache-Control", "public, max-age=31536000, immutable")
			} else {
				h.Set("Cache-Control", "no-cache")
			}
			s.static.ServeHTTP(w, r)
			return
		}
		// A missing asset is missing, not a page of the app's.
		if strings.HasPrefix(name, "assets/") {
			http.NotFound(w, r)
			return
		}
	}

	// The app's page, for its own routes: it decides what's at the path.
	h.Set("Content-Type", "text/html; charset=utf-8")
	h.Set("Cache-Control", "no-cache")
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = w.Write(s.page)
	}
}
