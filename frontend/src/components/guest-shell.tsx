import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"
import { Toaster } from "@/components/ui/sonner"
import { Candle } from "@/components/candle"

/** Around a page a guest with a shareable link sees: no sign-in, and no way
 * on to the rest of the calendar. It needs neither Clerk nor the app's
 * config, so a guest's page works whatever they do. */
export function GuestShell({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient())
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex min-h-dvh flex-col">
        <header className="border-b border-border/60 pt-[env(safe-area-inset-top)]">
          <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-2.5 px-4 sm:px-6">
            <Candle className="h-7 shrink-0" />
            <span className="truncate font-heading text-lg leading-none tracking-tight">House of Soft Beasts</span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-16 pt-6 sm:px-6">{children}</main>
        <footer className="mx-auto w-full max-w-5xl px-6 py-8 text-xs text-muted-foreground">
          House of Soft Beasts · Patentgatan 2, Stockholm
        </footer>
      </div>
      <Toaster theme="dark" position="top-center" />
    </QueryClientProvider>
  )
}
