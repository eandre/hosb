package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"testing/fstest"
)

var built = fstest.MapFS{
	"index.html":         {Data: []byte("<html><head><title>x</title></head><body></body></html>")},
	"favicon.svg":        {Data: []byte("<svg/>")},
	"assets/index-a1.js": {Data: []byte("console.log(1)")},
	"social-preview.jpg": {Data: []byte("jpeg")},
}

func get(t *testing.T, h http.Handler, method, target string) *httptest.ResponseRecorder {
	t.Helper()
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest(method, target, nil))
	return w
}

func TestTheAppsRoutesGetItsPage(t *testing.T) {
	s := newSite(built, nil)
	for _, target := range []string{"/", "/events/2026-11-26-house-dinner", "/s/x-abc", "/index.html"} {
		w := get(t, s, http.MethodGet, target)
		if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), "<title>House of Soft Beasts · Calendar</title>") {
			t.Fatalf("%s: %d %s", target, w.Code, w.Body.String())
		}
		if got := w.Header().Get("Cache-Control"); got != "no-cache" {
			t.Fatalf("%s: Cache-Control %q", target, got)
		}
	}
	if w := get(t, s, http.MethodPost, "/"); w.Code != http.StatusMethodNotAllowed {
		t.Fatalf("a POST to a page: %d", w.Code)
	}
}

func TestFilesAreServedAsTheyAre(t *testing.T) {
	s := newSite(built, nil)
	w := get(t, s, http.MethodGet, "/assets/index-a1.js")
	if w.Code != http.StatusOK || w.Body.String() != "console.log(1)" {
		t.Fatalf("asset: %d %q", w.Code, w.Body.String())
	}
	if got := w.Header().Get("Cache-Control"); !strings.Contains(got, "immutable") {
		t.Fatalf("an asset is cached for good, not %q", got)
	}
	if w := get(t, s, http.MethodGet, "/favicon.svg"); w.Header().Get("Cache-Control") != "no-cache" {
		t.Fatalf("a public file is revalidated, not %q", w.Header().Get("Cache-Control"))
	}
	if w := get(t, s, http.MethodGet, "/assets/gone-b2.js"); w.Code != http.StatusNotFound {
		t.Fatalf("a missing asset: %d", w.Code)
	}
}

func TestAnUnbuiltAppSaysSo(t *testing.T) {
	if w := get(t, newSite(fstest.MapFS{}, nil), http.MethodGet, "/"); w.Code != http.StatusServiceUnavailable {
		t.Fatalf("unbuilt: %d", w.Code)
	}
}

// The API is passed on, path, query, method, headers and body as they came,
// and nothing else is.
func TestOnlyTheAPIIsPassedOn(t *testing.T) {
	var seen *http.Request
	var body string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = r
		b, _ := io.ReadAll(r.Body)
		body = string(b)
		w.Header().Set("Location", "https://example.test/settings?google=connected")
		w.WriteHeader(http.StatusSeeOther)
	}))
	defer backend.Close()
	target, _ := url.Parse(backend.URL)
	h := handler(newSite(built, nil), apiProxy(target, http.DefaultTransport))

	req := httptest.NewRequest(http.MethodPost, "/api/events?x=1", strings.NewReader(`{"a":1}`))
	req.Header.Set("Authorization", "Bearer t")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if seen == nil || seen.Method != http.MethodPost || seen.URL.Path != "/api/events" || seen.URL.RawQuery != "x=1" {
		t.Fatalf("passed on as %+v", seen)
	}
	if seen.Header.Get("Authorization") != "Bearer t" || body != `{"a":1}` {
		t.Fatalf("headers or body lost: %q %q", seen.Header.Get("Authorization"), body)
	}
	// A redirect comes back as it went.
	if w.Code != http.StatusSeeOther || w.Header().Get("Location") != "https://example.test/settings?google=connected" {
		t.Fatalf("answer: %d %q", w.Code, w.Header().Get("Location"))
	}

	// Not the API, however it's written.
	for _, target := range []string{"/apiary", "/api/../internal/google-calendar/sync", "/settings"} {
		seen = nil
		get(t, h, http.MethodGet, target)
		if seen != nil {
			t.Fatalf("%s was passed on as %s", target, seen.URL.Path)
		}
	}
}
