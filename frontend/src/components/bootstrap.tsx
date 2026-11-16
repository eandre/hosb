"use client"

import { useEffect, useState, type ReactNode } from "react"
import { AppShell } from "@/components/app-shell"
import { Candle } from "@/components/candle"
import { request } from "@/lib/api"
import { SetupNeeded } from "@/views/setup-needed"

type State = { status: "loading" } | { status: "ready"; key: string } | { status: "failed"; error: string }

/** Starts the app once the API has said which Clerk instance to sign in
 * with: the key is the environment's, so one build serves every one. */
export function Bootstrap({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading" })

  useEffect(() => {
    request<{ clerkPublishableKey: string }>("/api/config")
      .then(({ clerkPublishableKey }) => setState({ status: "ready", key: clerkPublishableKey }))
      .catch((err: Error) =>
        setState({ status: "failed", error: `The calendar's API can't be reached: ${err.message}` }),
      )
  }, [])

  switch (state.status) {
    case "loading":
      return (
        <div className="flex min-h-dvh items-center justify-center">
          <Candle className="h-16 animate-pulse" />
        </div>
      )
    case "failed":
      return <SetupNeeded error={state.error} />
    case "ready":
      return state.key ? <AppShell publishableKey={state.key}>{children}</AppShell> : <SetupNeeded />
  }
}
