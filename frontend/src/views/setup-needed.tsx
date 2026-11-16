import { Candle } from "@/components/candle"

/** Shown when the app can't start: no Clerk publishable key is configured,
 * or the backend can't be reached. */
export function SetupNeeded({ error }: { error?: string }) {
  return (
    <section className="mx-auto flex min-h-dvh max-w-lg flex-col items-center justify-center px-6 text-center">
      <Candle className="mb-6 h-14 opacity-60" />
      <h1 className="text-2xl">The house isn't open yet</h1>
      {error ? (
        <p className="mt-3 text-sm text-muted-foreground">{error}</p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          No Clerk publishable key is configured. Set <code>clerk_publishable_key</code> in{" "}
          <code>backend/settings.config.toml</code>.
        </p>
      )}
    </section>
  )
}
