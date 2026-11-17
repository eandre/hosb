"use client"

import { CalendarDays, CheckCircle2, Clock, MapPin, Users } from "lucide-react"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useRef, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError, recordShareView, useGuestSignup, useShared, type Shared } from "@/lib/api"
import { formatLongDate, formatTimeRange } from "@/lib/dates"

/** An event shared through a link: all a guest with the link can see, and
 * where they sign up. */
export function SharePage() {
  // <slug>-<token>: the token finds the link, the slug is for reading.
  const token = useParams<{ link: string }>().link
  const { data, isPending, error } = useShared(token)
  const router = useRouter()

  // The event's slug may have changed since the link was made: show the
  // link as it reads now.
  useEffect(() => {
    if (data && data.path !== `/s/${token}`) router.replace(data.path)
  }, [data, token, router])

  // One view per page load: the API counts people by this browser's id.
  const counted = useRef(false)
  useEffect(() => {
    if (counted.current) return
    counted.current = true
    recordShareView(token).catch(() => undefined)
  }, [token])

  if (error) {
    return (
      <p className="py-16 text-center text-muted-foreground">
        {error instanceof ApiError && error.status === 404
          ? "This link doesn't lead anywhere. Ask whoever sent it for a new one."
          : error.message}
      </p>
    )
  }
  if (isPending) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    )
  }
  return <SharedEvent token={token} shared={data} />
}

function SharedEvent({ token, shared }: { token: string; shared: Shared }) {
  const { event } = shared
  return (
    <article className="mx-auto grid max-w-3xl gap-8 md:grid-cols-[minmax(0,1fr)_18rem] md:items-start">
      <div>
        <p className="text-sm text-muted-foreground">
          {shared.invitedBy ? `${shared.invitedBy} invited you to` : "You're invited to"}
        </p>
        <h1 className="mt-1 text-3xl leading-tight text-balance sm:text-4xl">{event.title}</h1>
        <dl className="mt-5 grid gap-3 text-sm">
          <div className="flex items-center gap-3">
            <CalendarDays className="size-4 text-candle" />
            <dt className="sr-only">Date</dt>
            <dd>{formatLongDate(event.startsAt)}</dd>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="size-4 text-candle" />
            <dt className="sr-only">Time</dt>
            <dd className="tabular-nums">{formatTimeRange(event.startsAt, event.endsAt)}</dd>
          </div>
          <div className="flex items-center gap-3">
            <MapPin className="size-4 text-candle" />
            <dt className="sr-only">Where</dt>
            <dd>
              {event.location ? `${event.location}, ` : ""}House of Soft Beasts, Patentgatan 2, Stockholm
            </dd>
          </div>
          {event.placesLeft !== null && !event.isOver && (
            <div className="flex items-center gap-3">
              <Users className="size-4 text-candle" />
              <dt className="sr-only">Places</dt>
              <dd>{event.placesLeft === 0 ? "No places left" : `${event.placesLeft} places left`}</dd>
            </div>
          )}
        </dl>
        {event.description && (
          <>
            <Separator className="my-6" />
            <p className="leading-relaxed whitespace-pre-line text-foreground/90">{event.description}</p>
          </>
        )}
      </div>
      <aside className="md:sticky md:top-20">
        {shared.signupsOpen ? (
          <SignupForm token={token} />
        ) : (
          <p className="rounded-2xl border border-border/70 bg-card/60 p-4 text-sm text-muted-foreground">
            {shared.closedReason ?? "Sign-ups are closed."}
          </p>
        )}
      </aside>
    </article>
  )
}

function SignupForm({ token }: { token: string }) {
  const signup = useGuestSignup(token)
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")

  function submit(e: FormEvent) {
    e.preventDefault()
    signup.mutate({ name, email })
  }

  if (signup.data) {
    return (
      <section className="rounded-2xl border border-candle/25 bg-card/80 p-5 text-center">
        <CheckCircle2 className="mx-auto mb-3 size-8 text-candle" />
        <h2 className="text-lg">
          {signup.data.status === "signed_up" ? "You're on the list" : "You were already on the list"}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">See you there, {signup.data.name.split(" ")[0]}.</p>
      </section>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="grid gap-4 rounded-2xl border border-candle/25 bg-card/80 p-4 shadow-[0_0_40px_-20px_rgba(232,165,75,0.5)]"
    >
      <h2 className="text-lg">Sign up as a guest</h2>
      <div className="grid gap-2">
        <Label htmlFor="guest-name">Full name</Label>
        <Input
          id="guest-name"
          required
          autoComplete="name"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="guest-email">Email</Label>
        <Input
          id="guest-email"
          type="email"
          required
          autoComplete="email"
          maxLength={254}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      {signup.error && (
        <p className="text-sm text-destructive" role="alert">
          {signup.error.message}
        </p>
      )}
      <Button type="submit" disabled={signup.isPending}>
        {signup.isPending ? "Signing you up…" : "Sign me up"}
      </Button>
    </form>
  )
}
