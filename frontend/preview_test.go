package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestOnlyEventAndLinkPagesHavePreviews(t *testing.T) {
	for path, want := range map[string]string{
		"/events/2026-11-26-house-dinner": "/internal/previews/events/2026-11-26-house-dinner",
		"/events/55":                      "/internal/previews/events/55",
		"/s/2026-11-26-house-dinner-abc":  "/internal/previews/share/2026-11-26-house-dinner-abc",
		"/":                               "",
		"/settings":                       "",
		"/events/":                        "",
		"/events/a/b":                     "",
		"/events/x%2Fy":                   "",
		"/s/../internal":                  "",
	} {
		if got := previewPath(path); got != want {
			t.Errorf("%s: %q, want %q", path, got, want)
		}
	}
}

func at(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t
}

func TestThePreviewSaysWhenInStockholm(t *testing.T) {
	end := at("2026-11-26T21:00:00Z")
	p := &preview{Title: "House Dinner", StartsAt: at("2026-11-26T17:00:00Z"), EndsAt: &end}
	if got := p.description(); got != "Thursday 26 November 2026, 18:00–22:00 · House of Soft Beasts, Stockholm" {
		t.Fatalf("description: %q", got)
	}
	who := "Lisa"
	p = &preview{Title: "Sauna", StartsAt: at("2026-07-01T16:30:00Z"), Location: "The garden", InvitedBy: &who}
	if got := p.description(); got != "Lisa invites you · Wednesday 1 July 2026, 18:30 · The garden, House of Soft Beasts, Stockholm" {
		t.Fatalf("description: %q", got)
	}
}

const page = `<!doctype html>
<html lang="en">
  <head>
    <meta name="description" content="The calendar." />
    <meta property="og:title" content="House of Soft Beasts · Calendar" />
    <meta name="twitter:card" content="summary" />
    <title>House of Soft Beasts · Calendar</title>
  </head>
  <body></body>
</html>`

func TestThePageCarriesTheEventsTags(t *testing.T) {
	out := string(withTags([]byte(page), &preview{Title: `Dinner & "Drinks" <3`, StartsAt: at("2026-11-26T17:00:00Z")}, "https://www.hosb.se", true))
	for _, want := range []string{
		`<title>Dinner &amp; &#34;Drinks&#34; &lt;3 · House of Soft Beasts</title>`,
		`<meta property="og:title" content="Dinner &amp; &#34;Drinks&#34; &lt;3" />`,
		`<meta property="og:description" content="Thursday 26 November 2026, 18:00 · House of Soft Beasts, Stockholm" />`,
		`<meta name="twitter:title" content="Dinner &amp; &#34;Drinks&#34; &lt;3" />`,
	} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %s in\n%s", want, out)
		}
	}
	// The page's own are replaced, not kept beside them.
	if n := strings.Count(out, `property="og:title"`); n != 1 {
		t.Errorf("%d og:title tags", n)
	}
	if strings.Contains(out, "The calendar.") || strings.Contains(out, "House of Soft Beasts · Calendar") {
		t.Errorf("the page's own tags are still there:\n%s", out)
	}
	if n := strings.Count(out, `name="twitter:card"`); n != 1 {
		t.Errorf("%d twitter:card tags", n)
	}
}

func TestEveryPageHasThePreviewImage(t *testing.T) {
	out := string(withTags([]byte(page), nil, "https://www.hosb.se", true))
	for _, want := range []string{
		`<title>House of Soft Beasts · Calendar</title>`,
		`<meta property="og:title" content="House of Soft Beasts · Calendar" />`,
		`<meta property="og:image" content="https://www.hosb.se/social-preview.jpg" />`,
		`<meta property="og:image:width" content="1200" />`,
		`<meta name="twitter:card" content="summary_large_image" />`,
	} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %s in\n%s", want, out)
		}
	}
	// Without an image, or an origin to give its address from: none.
	for _, out := range []string{
		string(withTags([]byte(page), nil, "https://www.hosb.se", false)),
		string(withTags([]byte(page), nil, "", true)),
	} {
		if strings.Contains(out, "og:image") || !strings.Contains(out, `content="summary"`) {
			t.Errorf("an image without one:\n%s", out)
		}
	}
}

func TestTheOriginIsWhereTheRequestCameIn(t *testing.T) {
	for _, c := range []struct {
		host, fwdHost, fwdProto, want string
	}{
		{"www.hosb.se", "", "", "https://www.hosb.se"},
		{"internal:8080", "www.hosb.se", "https", "https://www.hosb.se"},
		{"api.localhost:4000", "", "", "http://api.localhost:4000"},
		{"127.0.0.1:4000", "", "", "http://127.0.0.1:4000"},
		{"www.hosb.se", "", "http", "http://www.hosb.se"},
		{`evil"><script>`, "", "", ""},
	} {
		r := httptest.NewRequest(http.MethodGet, "/", nil)
		r.Host = c.host
		if c.fwdHost != "" {
			r.Header.Set("X-Forwarded-Host", c.fwdHost)
		}
		if c.fwdProto != "" {
			r.Header.Set("X-Forwarded-Proto", c.fwdProto)
		}
		if got := origin(r); got != c.want {
			t.Errorf("%+v: %q", c, got)
		}
	}
}

func TestPreviewsAreLookedUp(t *testing.T) {
	var asked []string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		asked = append(asked, r.URL.Path)
		switch r.URL.Path {
		case "/internal/previews/events/known":
			_, _ = w.Write([]byte(`{"title":"House Dinner","startsAt":"2026-11-26T17:00:00Z","endsAt":null,"location":""}`))
		case "/internal/previews/events/slow":
			time.Sleep(2 * previewTimeout)
		default:
			http.NotFound(w, r)
		}
	}))
	defer backend.Close()
	base, _ := url.Parse(backend.URL)
	look := fetchPreviews(backend.Client(), base)

	if p := look(context.Background(), "/events/known"); p == nil || p.Title != "House Dinner" {
		t.Fatalf("known: %+v", p)
	}
	if p := look(context.Background(), "/events/unknown"); p != nil {
		t.Fatalf("unknown: %+v", p)
	}
	start := time.Now()
	if p := look(context.Background(), "/events/slow"); p != nil || time.Since(start) > 2*previewTimeout {
		t.Fatalf("slow: %+v after %s", p, time.Since(start))
	}
	// Other pages aren't looked up at all.
	asked = nil
	if p := look(context.Background(), "/settings"); p != nil || len(asked) != 0 {
		t.Fatalf("settings: %+v, asked %v", p, asked)
	}

	// Served with it, the event's page carries its name.
	s := newSite(built, look)
	if w := get(t, s, http.MethodGet, "/events/known"); !strings.Contains(w.Body.String(), `content="House Dinner"`) {
		t.Fatalf("page: %s", w.Body.String())
	}
	// An event that isn't there: the calendar's own.
	if w := get(t, s, http.MethodGet, "/events/unknown"); !strings.Contains(w.Body.String(), `<meta property="og:title" content="House of Soft Beasts · Calendar" />`) {
		t.Fatalf("an unknown event's page: %s", w.Body.String())
	}
}
