package main

import (
	"io/fs"
	"net/http"
	"path"
	"strings"
)

// site serves a single-page app's built files: each file as it is, and the
// app's page, index.html, for every other path, the app's own routes, with
// an event's link preview in it on the event's pages (preview.go).
type site struct {
	files fs.FS
	// The app's page; nil if the app hasn't been built.
	page   []byte
	static http.Handler
	// Looks up a page's link preview; nil for none.
	preview previewer
	// Whether the build has the preview image (preview.go).
	image bool
}

// newSite serves the app built into files, with the previews preview looks
// up (nil for none).
func newSite(files fs.FS, preview previewer) *site {
	s := &site{files: files, static: http.FileServerFS(files), preview: preview}
	if _, err := fs.Stat(files, strings.TrimPrefix(previewImage, "/")); err == nil {
		s.image = true
	}
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
	var p *preview
	if s.preview != nil {
		p = s.preview(r.Context(), path.Clean("/"+r.URL.Path))
	}
	page := withTags(s.page, p, origin(r), s.image)
	h.Set("Content-Type", "text/html; charset=utf-8")
	h.Set("Cache-Control", "no-cache")
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = w.Write(page)
	}
}
