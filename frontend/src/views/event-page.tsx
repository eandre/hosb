import { ArrowLeft, CalendarDays, Clock, MapPin, Minus, Pencil, Plus, Trash2, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { DeleteEventDialog } from "@/components/delete-event-dialog"
import { EventFormModal } from "@/components/event-form"
import { ShareButton, ShareLinksPanel } from "@/components/share-link"
import { isOver, placesLeft, statusLabel } from "@/lib/events"
import {
  ApiError,
  useEvent,
  useMe,
  useRsvp,
  type Attendee,
  type EventDetail,
  type GuestSignup,
  type RSVPStatus,
} from "@/lib/api"
import { formatLongDate, formatTimeRange } from "@/lib/dates"
import { cn } from "@/lib/utils"



function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("") || "?"
}

export function EventPage() {
  const ref = useParams<{ slug: string }>().slug!
  const { data: event, isPending, error } = useEvent(ref)
  const { data: me } = useMe()
  const navigate = useNavigate()

  // Reached by an id, or a slug the event had: show its own address.
  useEffect(() => {
    if (event && event.slug !== ref) navigate(`/events/${event.slug}`, { replace: true })
  }, [event, ref, navigate])

  if (error) {
    return (
      <div className="py-16 text-center">
        <p className="text-muted-foreground">
          {error instanceof ApiError && error.status === 404 ? "This event doesn't exist, or was cancelled." : error.message}
        </p>
        <Button asChild variant="link" className="mt-2">
          <Link to="/">Back to the calendar</Link>
        </Button>
      </div>
    )
  }
  if (isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    )
  }

  const over = isOver(event)
  return (
    <article>
      <div className="mb-4 flex items-center justify-between gap-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/">
            <ArrowLeft /> Calendar
          </Link>
        </Button>
        <div className="flex gap-2">
          {!over && <ShareButton event={event} admin={me?.admin ?? false} />}
          {me?.admin && <AdminActions event={event} />}
        </div>
      </div>

      <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_20rem] md:items-start">
        <div>
          <h1 className="text-3xl leading-tight text-balance sm:text-4xl">{event.title}</h1>
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
            {event.location && (
              <div className="flex items-center gap-3">
                <MapPin className="size-4 text-candle" />
                <dt className="sr-only">Where</dt>
                <dd>{event.location}</dd>
              </div>
            )}
            <div className="flex items-center gap-3">
              <Users className="size-4 text-candle" />
              <dt className="sr-only">Attendance</dt>
              <dd>
                {event.goingCount} going
                {event.guestCount > 0 && ` (${event.guestCount} via shared links)`}
                {event.maybeCount > 0 && `, ${event.maybeCount} maybe`}
                {event.capacity !== null && ` · ${event.capacity} places, ${placesLeft(event)} left`}
              </dd>
            </div>
          </dl>
          {event.description && (
            <>
              <Separator className="my-6" />
              <p className="leading-relaxed whitespace-pre-line text-foreground/90">{event.description}</p>
            </>
          )}
        </div>

        <aside className="space-y-6 md:sticky md:top-20">
          {over ? (
            <p className="rounded-xl border border-border/70 bg-card/60 p-4 text-sm text-muted-foreground">
              This event is over.
              {event.myRsvp?.status === "going" && " Thank you for coming."}
            </p>
          ) : (
            <RsvpCard event={event} />
          )}
          <Attendees attendees={event.attendees} />
          <Guests guests={event.guestSignups} />
          {me?.admin && <ShareLinksPanel event={event} />}
        </aside>
      </div>
    </article>
  )
}

/** A guest's name as given: first and last, at least. */
const isFullName = (name: string) => name.trim().split(/\s+/).filter(Boolean).length >= 2

function RsvpCard({ event }: { event: EventDetail }) {
  const rsvp = useRsvp(event.id)
  const mine = event.myRsvp
  const saved = () => ({
    count: mine?.status === "going" ? mine.guests : 0,
    names: mine?.status === "going" ? mine.guestNames : [],
  })
  const [guests, setGuests] = useState(saved().count)
  const [names, setNames] = useState<string[]>(saved().names)
  const [checked, setChecked] = useState(false)
  const left = placesLeft(event)
  // Places this member could take: what's left plus what they hold now.
  const room = left === null ? Infinity : left + (mine?.status === "going" ? 1 + mine.guests : 0)
  const full = room < 1
  // Guests already brought under a higher limit stay; no more are added.
  const most = Math.max(event.maxGuests, saved().count)
  const required = event.guestNamesRequired

  const given = Array.from({ length: guests }, (_, i) => (names[i] ?? "").trim().replace(/\s+/g, " "))
  const missing = required ? given.map((n) => !isFullName(n)) : given.map(() => false)
  const changed =
    mine?.status === "going" &&
    (guests !== saved().count || given.filter(Boolean).join("\n") !== saved().names.join("\n"))

  function reset() {
    setGuests(saved().count)
    setNames(saved().names)
    setChecked(false)
  }

  function send(status: RSVPStatus | null) {
    if (status === "going" && missing.some(Boolean)) {
      setChecked(true)
      toast.error(guests === 1 ? "Give your guest's full name" : "Give each guest's full name")
      return
    }
    const payload = status
      ? {
          status,
          guests: status === "going" ? guests : 0,
          guestNames: status === "going" ? given.filter(Boolean) : [],
        }
      : null
    rsvp.mutate(payload, {
      onSuccess: () => {
        setChecked(false)
        if (payload?.status === "going") toast.success(changed ? "Guests saved" : "See you there")
        if (payload?.status !== "going") {
          setGuests(0)
          setNames([])
        }
      },
      onError: (err) => toast.error(err.message),
    })
  }

  function changeGuests(n: number) {
    setGuests(n)
    setNames((current) => current.slice(0, n))
  }

  return (
    <section className="rounded-2xl border border-candle/25 bg-card/80 p-4 shadow-[0_0_40px_-20px_rgba(232,165,75,0.5)]">
      <h2 className="mb-3 text-lg">Will you be there?</h2>
      <ToggleGroup
        type="single"
        variant="outline"
        spacing={0}
        className="w-full"
        value={mine?.status ?? ""}
        disabled={rsvp.isPending}
        onValueChange={(value) => {
          if (value) send(value as RSVPStatus)
        }}
      >
        {(["going", "maybe", "not_going"] as const).map((status) => (
          <ToggleGroupItem
            key={status}
            value={status}
            disabled={status === "going" && full && mine?.status !== "going"}
            className="flex-1 data-[state=on]:bg-candle data-[state=on]:text-primary-foreground"
          >
            {statusLabel[status]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      {full && mine?.status !== "going" && (
        <p className="mt-2 text-sm text-ember">The event is full.</p>
      )}

      {most > 0 && (
        <>
          <div className="mt-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm">Bringing guests</p>
              <p className="text-xs text-muted-foreground">
                Up to {event.maxGuests}, with your guest passes
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                aria-label="One guest fewer"
                disabled={guests === 0 || rsvp.isPending}
                onClick={() => changeGuests(guests - 1)}
              >
                <Minus />
              </Button>
              <span className="w-5 text-center tabular-nums" aria-live="polite">{guests}</span>
              <Button
                variant="outline"
                size="icon"
                aria-label="One more guest"
                disabled={guests >= event.maxGuests || guests + 1 >= room || rsvp.isPending}
                onClick={() => changeGuests(guests + 1)}
              >
                <Plus />
              </Button>
            </div>
          </div>

          {guests > 0 && (
            <div className="mt-3 grid gap-2">
              {Array.from({ length: guests }, (_, i) => (
                <div key={i} className="grid gap-1">
                  <Label htmlFor={`guest-${i}`} className="sr-only">
                    Guest {i + 1}&apos;s full name
                  </Label>
                  <Input
                    id={`guest-${i}`}
                    autoComplete="off"
                    maxLength={120}
                    value={names[i] ?? ""}
                    aria-invalid={checked && missing[i] ? true : undefined}
                    disabled={rsvp.isPending}
                    onChange={(e) =>
                      setNames((current) => {
                        const next = [...current]
                        while (next.length < guests) next.push("")
                        next[i] = e.target.value
                        return next
                      })
                    }
                    placeholder={
                      required ? `Guest ${i + 1}: first and last name` : `Guest ${i + 1}'s name (optional)`
                    }
                  />
                </div>
              ))}
              {checked && missing.some(Boolean) && (
                <p className="text-xs text-ember" role="alert">
                  This event asks for each guest&apos;s full name, for the door list.
                </p>
              )}
            </div>
          )}

          {changed && (
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="ghost" size="sm" disabled={rsvp.isPending} onClick={reset}>
                Cancel
              </Button>
              <Button size="sm" disabled={rsvp.isPending} onClick={() => send("going")}>
                Save guests
              </Button>
            </div>
          )}
        </>
      )}

      {mine && (
        <Button variant="link" size="sm" className="mt-2 h-auto px-0 text-muted-foreground" onClick={() => send(null)}>
          Withdraw my answer
        </Button>
      )}
    </section>
  )
}

function Attendees({ attendees }: { attendees: Attendee[] }) {
  if (attendees.length === 0) {
    return <p className="text-sm text-muted-foreground">No one has answered yet. Be the first.</p>
  }
  const groups = (["going", "maybe", "not_going"] as const)
    .map((status) => ({ status, people: attendees.filter((a) => a.status === status) }))
    .filter((g) => g.people.length > 0)
  return (
    <section className="space-y-5">
      {groups.map(({ status, people }) => (
        <div key={status}>
          <h3 className="mb-2 text-sm font-sans font-medium text-muted-foreground">
            {statusLabel[status]} · {people.length}
          </h3>
          <ul className="space-y-2">
            {people.map((a) => (
              <li key={a.userId} className={cn(status === "not_going" && "opacity-60")}>
                <div className="flex items-center gap-3">
                  <Avatar className="size-8">
                    <AvatarImage src={a.imageUrl || undefined} alt="" />
                    <AvatarFallback className="text-xs">{initials(a.name)}</AvatarFallback>
                  </Avatar>
                  <span className="min-w-0 flex-1 truncate text-sm">{a.name || "A member"}</span>
                  {a.guests > 0 && <span className="text-xs text-muted-foreground">+{a.guests}</span>}
                </div>
                {a.guestNames.length > 0 && (
                  <p className="mt-0.5 pl-11 text-xs text-muted-foreground">With {a.guestNames.join(", ")}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}

function Guests({ guests }: { guests: GuestSignup[] }) {
  if (guests.length === 0) return null
  return (
    <section>
      <h3 className="mb-2 text-sm font-sans font-medium text-muted-foreground">
        Guests via shared links · {guests.length}
      </h3>
      <ul className="space-y-2">
        {guests.map((g, i) => (
          <li key={`${g.name}-${i}`} className="flex items-center gap-3">
            <Avatar className="size-8">
              <AvatarFallback className="text-xs">{initials(g.name)}</AvatarFallback>
            </Avatar>
            <span className="min-w-0 flex-1 truncate text-sm">{g.name}</span>
            {g.invitedBy && (
              <span className="truncate text-xs text-muted-foreground">via {g.invitedBy.split(" ")[0]}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function AdminActions({ event }: { event: EventDetail }) {
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
        <Pencil /> Edit
      </Button>
      <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleting(true)}>
        <Trash2 /> <span className="sr-only sm:not-sr-only">Delete</span>
      </Button>
      <EventFormModal
        open={editing}
        onOpenChange={setEditing}
        event={event}
        // A new title or date is a new slug, and with it a new address.
        onSaved={(saved) => navigate(`/events/${saved.slug}`, { replace: true })}
      />
      <DeleteEventDialog event={event} open={deleting} onOpenChange={setDeleting} onDeleted={() => navigate("/")} />
    </div>
  )
}
