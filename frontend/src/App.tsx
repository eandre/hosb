import { ClerkProvider, ClerkFailed, ClerkLoaded, ClerkLoading, Show } from "@clerk/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes } from "react-router"
import { Toaster } from "@/components/ui/sonner"
import { SiteHeader } from "@/components/site-header"
import { Candle } from "@/components/candle"
import { ApiError } from "@/lib/api"
import { EventsPage } from "@/pages/events-page"
import { AdminPage } from "@/pages/admin-page"
import { EventPage } from "@/pages/event-page"
import { Landing } from "@/pages/landing"
import { SetupNeeded } from "@/pages/setup-needed"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A 4xx won't get better by asking again.
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

// Clerk's own screens, in the house's colours.
const appearance = {
  variables: {
    colorPrimary: "#e8a54b",
    colorPrimaryForeground: "#1a130b",
    colorBackground: "#1d1814",
    colorForeground: "#f3eadb",
    colorMutedForeground: "#b3a593",
    colorInput: "#241e18",
    colorInputForeground: "#f3eadb",
    colorNeutral: "#f3eadb",
    colorDanger: "#e5604d",
    fontFamily: "'Geist Variable', sans-serif",
    borderRadius: "0.75rem",
  },
}

export function App({ publishableKey }: { publishableKey: string }) {
  return (
    <ClerkProvider publishableKey={publishableKey} appearance={appearance} afterSignOutUrl="/">
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <div className="flex min-h-dvh flex-col">
            <SiteHeader />
            <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-28 pt-4 sm:px-6 md:pb-12">
              <ClerkLoading>
                <div className="flex justify-center py-24">
                  <Candle className="h-16 animate-pulse" />
                </div>
              </ClerkLoading>
              <ClerkFailed>
                <SetupNeeded error="Clerk could not be loaded, so you can't sign in right now. Check your connection and try again." />
              </ClerkFailed>
              <ClerkLoaded>
                <Show when="signed-out">
                  <Landing />
                </Show>
                <Show when="signed-in">
                  <Routes>
                    <Route path="/" element={<EventsPage />} />
                    <Route path="/events/:id" element={<EventPage />} />
                    <Route path="/admin" element={<AdminPage />} />
                    <Route path="*" element={<EventsPage />} />
                  </Routes>
                </Show>
              </ClerkLoaded>
            </main>
            <footer className="mx-auto hidden w-full max-w-5xl px-6 py-8 text-xs text-muted-foreground md:block">
              House of Soft Beasts · Patentgatan 2, Stockholm
            </footer>
          </div>
          <Toaster theme="dark" position="top-center" />
        </BrowserRouter>
      </QueryClientProvider>
    </ClerkProvider>
  )
}
