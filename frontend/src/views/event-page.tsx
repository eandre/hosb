import { ArrowLeft, CalendarDays, Clock, MapPin, Minus, Pencil, Plus, Trash2, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { DeleteEventDialog } from "@/components/delete-event-dialog"
import { EventFormModal } from "@/components/event-form"
import { ShareButton, ShareLinksPanel } from "@/components/share-link"
import { placesLeft, statusLabel } from "@/lib/events"
import {
  ApiError,
  MAX_GUESTS,
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

const DEFAULT_DURATION_MS = 3 * 60 * 60 * 1000

function isOver(event: EventDetail) {
  const end = event.endsAt ? new Date(event.endsAt) : new Date(new Date(event.startsAt).getTime() + DEFAULT_DURATION_MS)
  return end < new Date()
}

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

function RsvpCard({ event }: { event: EventDetail }) {
  const rsvp = useRsvp(event.id)
  const mine = event.myRsvp
  const [guests, setGuests] = useState(mine?.guests ?? 0)
  const left = placesLeft(event)
  // Places this member could take: what's left plus what they hold now.
  const room = left === null ? Infinity : left + (mine?.status === "going" ? 1 + mine.guests : 0)
  const full = room < 1

  function send(status: RSVPStatus | null, nextGuests = guests) {
    const payload = status ? { status, guests: status === "going" ? nextGuests : 0 } : null
    rsvp.mutate(payload, {
      onSuccess: () => {
        if (payload?.status === "going") toast.success("See you there")
      },
      onError: (err) => {
        toast.error(err.message)
        setGuests(mine?.guests ?? 0)
      },
    })
  }

  function changeGuests(n: number) {
    setGuests(n)
    if (mine?.status === "going") send("going", n)
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

      <div className="mt-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm">Bringing guests</p>
          <p className="text-xs text-muted-foreground">Up to {MAX_GUESTS}, with your guest passes</p>
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
            disabled={guests >= MAX_GUESTS || guests + 1 >= room || rsvp.isPending}
            onClick={() => changeGuests(guests + 1)}
          >
            <Plus />
          </Button>
        </div>
      </div>

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
              <li key={a.userId} className={cn("flex items-center gap-3", status === "not_going" && "opacity-60")}>
                <Avatar className="size-8">
                  <AvatarImage src={a.imageUrl || undefined} alt="" />
                  <AvatarFallback className="text-xs">{initials(a.name)}</AvatarFallback>
                </Avatar>
                <span className="min-w-0 flex-1 truncate text-sm">{a.name || "A member"}</span>
                {a.guests > 0 && <span className="text-xs text-muted-foreground">+{a.guests}</span>}
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
