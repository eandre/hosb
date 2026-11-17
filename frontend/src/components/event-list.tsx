import { ChevronRight, MapPin, Users } from "lucide-react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import type { CalendarEvent, RSVPStatus } from "@/lib/api"
import { formatDay, formatTimeRange, groupByDay } from "@/lib/dates"
import { placesLeft, statusLabel } from "@/lib/events"
import { cn } from "@/lib/utils"

export function RsvpBadge({ status }: { status: RSVPStatus }) {
  return (
    <Badge
      variant={status === "going" ? "default" : status === "maybe" ? "secondary" : "outline"}
      className="shrink-0"
    >
      {statusLabel[status]}
    </Badge>
  )
}

export function EventRow({ event, past }: { event: CalendarEvent; past?: boolean }) {
  const left = placesLeft(event)
  return (
    <Link
      href={`/events/${event.slug}`}
      className={cn(
        "group flex items-center gap-4 rounded-xl border border-border/70 bg-card/70 p-4 transition-colors",
        "hover:border-candle/40 hover:bg-accent/60 focus-visible:outline-2 focus-visible:outline-ring",
        past && "opacity-75",
      )}
    >
      <div className="w-14 shrink-0 text-sm tabular-nums text-candle">
        {formatTimeRange(event.startsAt, null)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-2 min-w-0 text-lg leading-snug text-pretty break-words">{event.title}</h3>
          {event.myRsvp && <RsvpBadge status={event.myRsvp.status} />}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {event.location && (
            <span className="flex min-w-0 items-center gap-1">
              <MapPin className="size-3.5 shrink-0" />
              <span className="truncate">{event.location}</span>
            </span>
          )}
          <span className="flex items-center gap-1">
            <Users className="size-3.5" />
            {event.goingCount} going
            {left !== null && !past && (
              <span className={cn(left === 0 && "text-ember")}>
                {" · "}
                {left === 0 ? "full" : `${left} left`}
              </span>
            )}
          </span>
        </div>
      </div>
      <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  )
}

/** Events under a heading for each day. */
export function EventList({ events, past, empty }: { events: CalendarEvent[]; past?: boolean; empty: string }) {
  if (events.length === 0) {
    return <p className="py-16 text-center text-muted-foreground">{empty}</p>
  }
  return (
    <div className="space-y-8">
      {groupByDay(events).map(({ day, items }) => (
        <section key={day.toISOString()}>
          <h2 className="sticky top-14 z-10 -mx-4 mb-3 bg-background/85 px-4 py-2 text-base text-muted-foreground backdrop-blur sm:mx-0 sm:px-0">
            {formatDay(day)}
          </h2>
          <div className="space-y-3">
            {items.map((event) => (
              <EventRow key={event.id} event={event} past={past} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export function EventListSkeleton() {
  return (
    <div className="space-y-3" aria-busy>
      <Skeleton className="h-5 w-40" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-20 w-full rounded-xl" />
      ))}
    </div>
  )
}
