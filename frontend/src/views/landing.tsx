import { SignInButton } from "@clerk/react"
import { Button } from "@/components/ui/button"
import { Candle } from "@/components/candle"

export function Landing() {
  return (
    <section className="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <Candle className="mb-8 h-20" />
      <p className="text-sm uppercase tracking-[0.25em] text-muted-foreground">Members' calendar</p>
      <h1 className="mt-3 text-4xl leading-tight sm:text-5xl">A candlelit space in Stockholm</h1>
      <p className="mt-5 text-balance text-muted-foreground">
        Days for slow work and connection. Evenings for gatherings, performances, and ritual.
        Sign in to see what's coming up at the house, and tell us if you'll be there.
      </p>
      <SignInButton mode="modal">
        <Button size="lg" className="mt-8 w-full sm:w-auto">
          Sign in
        </Button>
      </SignInButton>
    </section>
  )
}
