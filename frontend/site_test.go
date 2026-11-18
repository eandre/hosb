package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"
)

var built = fstest.MapFS{
	"index.html":         {Data: []byte("<html><head><title>x</title></head><body></body></html>")},
	"favicon.svg":        {Data: []byte("<svg/>")},
	"assets/index-a1.js": {Data: []byte("console.log(1)")},
}

func get(t *testing.T, s *site, target string) *httptest.ResponseRecorder {
	t.Helper()
	w := httptest.NewRecorder()
	s.ServeHTTP(w, httptest.NewRequest(http.MethodGet, target, nil))
	return w
}

func TestTheAppsRoutesGetItsPage(t *testing.T) {
	s, err := newSite(built, "http://api.localhost:4000")
	if err != nil {
		t.Fatal(err)
	}
	for _, target := range []string{"/", "/events/2026-11-26-house-dinner", "/s/x-abc", "/index.html", "/../etc/passwd"} {
		w := get(t, s, target)
		if w.Code != http.StatusOK {
			t.Fatalf("%s: %d", target, w.Code)
		}
		body := w.Body.String()
		if !strings.Contains(body, `<script>window.hosb = {"apiURL":"http://api.localhost:4000"}</script>`) {
			t.Fatalf("%s: the page isn't told where the API is: %s", target, body)
		}
		if got := w.Header().Get("Cache-Control"); got != "no-cache" {
			t.Fatalf("%s: Cache-Control %q", target, got)
		}
	}
}

func TestFilesAreServedAsTheyAre(t *testing.T) {
	s, _ := newSite(built, "http://api.localhost:4000")
	w := get(t, s, "/assets/index-a1.js")
	if w.Code != http.StatusOK || w.Body.String() != "console.log(1)" {
		t.Fatalf("asset: %d %q", w.Code, w.Body.String())
	}
	if got := w.Header().Get("Cache-Control"); !strings.Contains(got, "immutable") {
		t.Fatalf("an asset is cached for good, not %q", got)
	}
	if w := get(t, s, "/favicon.svg"); w.Header().Get("Cache-Control") != "no-cache" {
		t.Fatalf("a public file is revalidated, not %q", w.Header().Get("Cache-Control"))
	}
	if w := get(t, s, "/assets/gone-b2.js"); w.Code != http.StatusNotFound {
		t.Fatalf("a missing asset: %d", w.Code)
	}
}

func TestTheConfigCantEndItsScript(t *testing.T) {
	s, _ := newSite(built, "https://x</script><script>alert(1)")
	if body := get(t, s, "/").Body.String(); strings.Contains(body, "</script><script>alert") {
		t.Fatalf("the URL ended the script: %s", body)
	}
}

func TestAnUnbuiltAppSaysSo(t *testing.T) {
	s, err := newSite(fstest.MapFS{}, "http://api.localhost:4000")
	if err != nil {
		t.Fatal(err)
	}
	if w := get(t, s, "/"); w.Code != http.StatusServiceUnavailable {
		t.Fatalf("unbuilt: %d", w.Code)
	}
}
