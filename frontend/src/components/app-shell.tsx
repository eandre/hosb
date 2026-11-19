import { ClerkFailed, ClerkLoaded, ClerkLoading, ClerkProvider, Show } from "@clerk/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"
import { Toaster } from "@/components/ui/sonner"
import { Candle } from "@/components/candle"
import { ErrorBoundary } from "@/components/error-boundary"
import { SiteFooter } from "@/components/site-footer"
import { SiteHeader } from "@/components/site-header"
import { ApiError } from "@/lib/api"
import { Landing } from "@/views/landing"
import { SetupNeeded } from "@/views/setup-needed"

const CLERK_UNAVAILABLE =
  "Clerk could not be loaded, so you can't sign in right now. Check your connection and try again."

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

/** Everything around a page: sign-in, data fetching, the header. Signed-out
 * visitors see the landing page instead of the page they asked for. */
export function AppShell({ publishableKey, children }: { publishableKey: string; children: ReactNode }) {
  // One client per browser session, not one per server render.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            // A 4xx won't get better by asking again.
            retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
          },
        },
      }),
  )

  return (
    <ErrorBoundary
      fallback={(err) => (
        <SetupNeeded error={err.message.includes("Clerk") ? CLERK_UNAVAILABLE : `Something went wrong: ${err.message}`} />
      )}
    >
      <ClerkProvider publishableKey={publishableKey} appearance={appearance} afterSignOutUrl="/">
        <QueryClientProvider client={queryClient}>
          <div className="flex min-h-dvh flex-col">
            <SiteHeader />
            <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-28 pt-4 sm:px-6 md:pb-12">
              <ClerkLoading>
                <div className="flex justify-center py-24">
                  <Candle className="h-16 animate-pulse" />
                </div>
              </ClerkLoading>
              <ClerkFailed>
                <SetupNeeded error={CLERK_UNAVAILABLE} />
              </ClerkFailed>
              <ClerkLoaded>
                <Show when="signed-out">
                  <Landing />
                </Show>
                <Show when="signed-in">{children}</Show>
              </ClerkLoaded>
            </main>
            <SiteFooter className="hidden md:block" />
          </div>
          <Toaster theme="dark" position="top-center" />
        </QueryClientProvider>
      </ClerkProvider>
    </ErrorBoundary>
  )
}
