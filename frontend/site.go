package main

import (
	"io/fs"
	"net/http"
	"path"
	"strings"
)

// site serves a single-page app's built files: each file as it is, and the
// app's page, index.html, for every other path, the app's own routes.
type site struct {
	files fs.FS
	// The app's page; nil if the app hasn't been built.
	page   []byte
	static http.Handler
}

// newSite serves the app built into files.
func newSite(files fs.FS) *site {
	s := &site{files: files, static: http.FileServerFS(files)}
	if page, err := fs.ReadFile(files, "index.html"); err == nil {
		s.page = page
	}
	return s
}

func (s *site) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if s.page == nil {
		// Unbuilt: every request says so, rather than the program not starting.
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
