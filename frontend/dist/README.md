The Vite build goes in `app/` here (`bun run build`), which the web service
embeds: see `../main.go`. This file keeps the directory, which the embed
needs, in a checkout that hasn't built the app.
