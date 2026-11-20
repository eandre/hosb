package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html"
	"log/slog"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
	_ "time/tzdata" // Stockholm's time zone, whatever the image holds
)

// A link to an event shows its name and when it is where it's shared
// (WhatsApp, Slack, iMessage): those apps read the page's own HTML and run
// none of its scripts, so the page is served with them in its tags. The
// community service says what they are (backend/previews.py).

// preview is what a link to an event shows.
type preview struct {
	Title     string     `json:"title"`
	StartsAt  time.Time  `json:"startsAt"`
	EndsAt    *time.Time `json:"endsAt"`
	Location  string     `json:"location"`
	InvitedBy *string    `json:"invitedBy"`
}

// previewer looks up the preview of the page at path, or returns nil for a
// page that has none, as one of no event's.
type previewer func(ctx context.Context, path string) *preview

// ref is an event's slug or id, or a shareable link's <slug>-<token>.
var ref = regexp.MustCompile(`^[A-Za-z0-9-]{1,200}$`)

// previewPath is where the community service has the preview of the page at
// path: an event's page, or a shareable link's. Empty for any other page.
func previewPath(path string) string {
	for prefix, api := range map[string]string{
		"/events/": "/internal/previews/events/",
		"/s/":      "/internal/previews/share/",
	} {
		if name, ok := strings.CutPrefix(path, prefix); ok && ref.MatchString(name) {
			return api + name
		}
	}
	return ""
}

// previewTimeout keeps a slow lookup from holding up the page: without its
// preview, it is the app's page as ever.
const previewTimeout = 1500 * time.Millisecond

// fetchPreviews looks previews up from the community service, at base, with
// client.
func fetchPreviews(client *http.Client, base *url.URL) previewer {
	return func(ctx context.Context, path string) *preview {
		api := previewPath(path)
		if api == "" {
			return nil
		}
		ctx, cancel := context.WithTimeout(ctx, previewTimeout)
		defer cancel()
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, base.JoinPath(api).String(), nil)
		if err != nil {
			return nil
		}
		resp, err := client.Do(req)
		if err != nil {
			slog.WarnContext(ctx, "looking up a page's preview failed", "path", path, "err", err)
			return nil
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			if resp.StatusCode != http.StatusNotFound {
				slog.WarnContext(ctx, "looking up a page's preview failed", "path", path, "status", resp.StatusCode)
			}
			return nil
		}
		var p preview
		if err := json.NewDecoder(resp.Body).Decode(&p); err != nil {
			return nil
		}
		return &p
	}
}

var stockholm = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Stockholm")
	if err != nil {
		panic(err)
	}
	return loc
}()

// when is the event's date and time as the app shows them: "Thursday 26
// November 2026, 18:00–22:00".
func (p *preview) when() string {
	start := p.StartsAt.In(stockholm)
	s := start.Format("Monday 2 January 2006, 15:04")
	if p.EndsAt != nil {
		end := p.EndsAt.In(stockholm)
		if end.YearDay() == start.YearDay() && end.Year() == start.Year() {
			s += "–" + end.Format("15:04")
		}
	}
	return s
}

// description is what the preview says below the event's name.
func (p *preview) description() string {
	where := "House of Soft Beasts, Stockholm"
	if p.Location != "" {
		where = p.Location + ", House of Soft Beasts, Stockholm"
	}
	d := p.when() + " · " + where
	if p.InvitedBy != nil && *p.InvitedBy != "" {
		d = *p.InvitedBy + " invites you · " + d
	}
	return d
}

var (
	titleTag = regexp.MustCompile(`<title>[^<]*</title>`)
	// The page's own description and link-preview tags, which these replace.
	metaTags = regexp.MustCompile(`\s*<meta (?:name|property)="(?:description|og:[a-z_:]+|twitter:[a-z_:]+)" content="[^"]*"\s*/?>`)
	// A host as a request may name it: a name or address, and a port.
	hostName = regexp.MustCompile(`^[A-Za-z0-9.-]+(?::[0-9]+)?$`)
)

const (
	siteTitle       = "House of Soft Beasts · Calendar"
	siteDescription = "The members' calendar of the House of Soft Beasts, a candlelit space in Stockholm."
	// The preview image, in public/: a JPEG made from social-preview.png,
	// small enough for WhatsApp, which skips images over about 300 KB.
	previewImage    = "/social-preview.jpg"
	previewImageAlt = "The House of Soft Beasts: a candlelit space in Stockholm."
)

// origin is where the request came in, as the browser or the app reading
// the page has it, for the absolute URLs link-preview tags need. Empty if
// the request doesn't say.
func origin(r *http.Request) string {
	host := r.Header.Get("X-Forwarded-Host")
	if host == "" {
		host = r.Host
	}
	if !hostName.MatchString(host) {
		return ""
	}
	scheme := r.Header.Get("X-Forwarded-Proto")
	if scheme != "http" && scheme != "https" {
		scheme = "https"
		name := strings.Split(host, ":")[0]
		if name == "localhost" || strings.HasSuffix(name, ".localhost") || name == "127.0.0.1" {
			scheme = "http"
		}
	}
	return scheme + "://" + host
}

// withTags is page with its title, description and link-preview tags: the
// event's name and date, if p is one's, else the calendar's own; and the
// preview image at origin, if there is one. Every value is escaped, as an
// event's name is whatever an admin gave it.
func withTags(page []byte, p *preview, origin string, image bool) []byte {
	title, fullTitle, description := siteTitle, siteTitle, siteDescription
	if p != nil {
		title, fullTitle, description = p.Title, p.Title+" · House of Soft Beasts", p.description()
	}
	title, fullTitle, description = html.EscapeString(title), html.EscapeString(fullTitle), html.EscapeString(description)

	tags := []string{
		fmt.Sprintf(`<meta name="description" content="%s" />`, description),
		`<meta property="og:type" content="website" />`,
		`<meta property="og:site_name" content="House of Soft Beasts" />`,
		fmt.Sprintf(`<meta property="og:title" content="%s" />`, title),
		fmt.Sprintf(`<meta property="og:description" content="%s" />`, description),
		fmt.Sprintf(`<meta name="twitter:title" content="%s" />`, title),
		fmt.Sprintf(`<meta name="twitter:description" content="%s" />`, description),
	}
	if image && origin != "" {
		url := html.EscapeString(origin + previewImage)
		tags = append(tags,
			fmt.Sprintf(`<meta property="og:image" content="%s" />`, url),
			`<meta property="og:image:type" content="image/jpeg" />`,
			`<meta property="og:image:width" content="1200" />`,
			`<meta property="og:image:height" content="630" />`,
			fmt.Sprintf(`<meta property="og:image:alt" content="%s" />`, html.EscapeString(previewImageAlt)),
			`<meta name="twitter:card" content="summary_large_image" />`,
			fmt.Sprintf(`<meta name="twitter:image" content="%s" />`, url),
		)
	} else {
		tags = append(tags, `<meta name="twitter:card" content="summary" />`)
	}

	out := metaTags.ReplaceAll(page, nil)
	out = titleTag.ReplaceAllLiteral(out, []byte(fmt.Sprintf("<title>%s</title>", fullTitle)))
	return bytes.Replace(out, []byte("</head>"), []byte("    "+strings.Join(tags, "\n    ")+"\n  </head>"), 1)
}
