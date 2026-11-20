import { ChevronLeft, ChevronRight, Clock, MapPin, Users } from "lucide-react"
import { useLayoutEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { RsvpBadge } from "@/components/event-list"
import { useEventsBetween, type CalendarEvent } from "@/lib/api"
import {
  addDays,
  dayKey,
  formatDay,
  formatTimeRange,
  formatWeekRange,
  groupByDay,
  parseDay,
  weekNumber,
  weekStart,
} from "@/lib/dates"
import { isOver, placesLeft } from "@/lib/events"
import { cn } from "@/lib/utils"


/** The house's weekly open hours, which come round every week: they go
 * together below the week's own events. */
const isHouseHours = (event: CalendarEvent) => /^house hours\b/i.test(event.title.trim())


/** A week of the calendar, Monday first: its events day by day, each in
 * full, and the House Hours together at the bottom. The week is the one of
 * the URL's ?date=, so that a reload keeps it; without one, this week. */
export function WeekView() {
  const [params, setParams] = useSearchParams()
  const start = weekStart(parseDay(params.get("date")) ?? new Date())
  const { data: events, isPending, error } = useEventsBetween(start, addDays(start, 7))
  const thisWeek = dayKey(start) === dayKey(weekStart(new Date()))

  function go(monday: Date) {
    const current = dayKey(monday) === dayKey(weekStart(new Date()))
    setParams(current ? {} : { date: dayKey(monday) }, { replace: true })
  }

  const own = (events ?? []).filter((e) => !isHouseHours(e))
  const hours = (events ?? []).filter(isHouseHours)

  return (
    <div className="space-y-8">
      <div className="flex items-stretch justify-between gap-2 rounded-2xl border border-border/70 bg-card/60 p-1.5">
        <Button
          variant="ghost"
          className="h-auto min-h-14 w-14 rounded-xl sm:w-20"
          onClick={() => go(addDays(start, -7))}
          aria-label="Previous week"
        >
          <ChevronLeft className="size-5" />
        </Button>
        <div className="flex min-w-0 flex-col justify-center py-2 text-center">
          <p className="text-xs tracking-[0.18em] text-candle uppercase">
            {thisWeek ? "This week" : `Week ${weekNumber(start)}`}
          </p>
          <h2 className="text-lg sm:text-xl">{formatWeekRange(start)}</h2>
        </div>
        <div className="flex items-stretch gap-1">
          {!thisWeek && (
            <Button
              variant="ghost"
              className="hidden h-auto rounded-xl px-4 sm:inline-flex"
              onClick={() => go(weekStart(new Date()))}
            >
              Today
            </Button>
          )}
          <Button
            variant="ghost"
            className="h-auto min-h-14 w-14 rounded-xl sm:w-20"
            onClick={() => go(addDays(start, 7))}
            aria-label="Next week"
          >
            <ChevronRight className="size-5" />
          </Button>
        </div>
      </div>

      {error ? (
        <p className="py-8 text-destructive">{error.message}</p>
      ) : isPending ? (
        <WeekSkeleton />
      ) : (
        <>
          {own.length === 0 ? (
            <p className="py-10 text-center text-muted-foreground">
              {hours.length > 0 ? "No special events this week, but the house is open." : "Nothing is planned this week."}
            </p>
          ) : (
            <div className="space-y-8">
              {groupByDay(own).map(({ day, items }) => (
                <section key={dayKey(day)} className="grid gap-3 sm:grid-cols-[4.5rem_minmax(0,1fr)] sm:gap-5">
                  <DayMark day={day} />
                  <div className="space-y-4">
                    {items.map((event) => (
                      <EventCard key={event.id} event={event} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
          {hours.length > 0 && <HouseHours events={hours} />}
        </>
      )}
    </div>
  )
}

/** The day's name and date, as a column beside its events. */
function DayMark({ day }: { day: Date }) {
  const today = dayKey(day) === dayKey(new Date())
  return (
    <h3 className="flex items-baseline gap-2 sm:sticky sm:top-20 sm:flex-col sm:items-start sm:gap-0 sm:self-start">
      <span className={cn("text-xs tracking-[0.18em] uppercase", today ? "text-candle" : "text-muted-foreground")}>
        {today ? "Today" : day.toLocaleDateString("en-GB", { weekday: "short" })}
      </span>
      <span className="font-heading text-2xl leading-none sm:text-4xl">{day.getDate()}</span>
      <span className="text-sm text-muted-foreground sm:text-xs">{day.toLocaleDateString("en-GB", { month: "short" })}</span>
    </h3>
  )
}

function EventCard({ event }: { event: CalendarEvent }) {
  const left = placesLeft(event)
  const over = isOver(event)
  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border/70 bg-card/70 p-5 transition-colors hover:border-candle/40 sm:p-6",
        "before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-gradient-to-r before:from-transparent before:via-candle/50 before:to-transparent",
        over && "opacity-70",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="flex items-center gap-1.5 text-candle tabular-nums">
          <Clock className="size-3.5" />
          {formatTimeRange(event.startsAt, event.endsAt)}
        </span>
        {event.location && (
          <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
            <MapPin className="size-3.5 shrink-0" />
            <span className="truncate">{event.location}</span>
          </span>
        )}
        {event.myRsvp && (
          <span className="ml-auto">
            <RsvpBadge status={event.myRsvp.status} />
          </span>
        )}
      </div>

      <h4 className="mt-2 font-heading text-2xl leading-tight text-pretty break-words sm:text-[1.7rem]">
        <Link
          to={`/events/${event.slug}`}
          className="rounded-sm decoration-candle/60 underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {event.title}
        </Link>
      </h4>

      {event.description && <Description text={event.description} className="mt-3" />}

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-border/60 pt-3 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Users className="size-3.5" />
          {event.goingCount} going
          {left !== null && !over && (
            <span className={cn(left === 0 && "text-ember")}>
              {" · "}
              {left === 0 ? "full" : `${left} left`}
            </span>
          )}
        </span>
        <Link to={`/events/${event.slug}`} className="flex items-center gap-0.5 text-foreground/80 hover:text-candle">
          {over ? "View" : event.myRsvp ? "Details" : "RSVP"}
          <ChevronRight className="size-4" />
        </Link>
      </div>
    </article>
  )
}

/** Text cut off after a few lines, with a way to read the rest. */
function Description({ text, lines = 4, className }: { text: string; lines?: 2 | 4; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null)
  const [open, setOpen] = useState(false)
  const [cut, setCut] = useState(false)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el || open) return
    const measure = () => setCut(el.scrollHeight > el.clientHeight + 1)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [text, open])

  return (
    <div className={className}>
      <p
        ref={ref}
        className={cn(
          "leading-relaxed whitespace-pre-line text-foreground/85",
          !open && (lines === 2 ? "line-clamp-2" : "line-clamp-4"),
        )}
      >
        {/* Cut, paragraphs follow on, so the cut never falls on a blank line. */}
        {open ? text : text.replace(/\n\s*\n/g, "\n")}
      </p>
      {(cut || open) && (
        <button
          type="button"
          className="mt-1 text-sm text-candle hover:underline focus-visible:outline-2 focus-visible:outline-ring"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? "Show less" : "Read more"}
        </button>
      )}
    </div>
  )
}

/** The week's House Hours: when the house is open, day by day, and what
 * they are once if every one says the same. */
function HouseHours({ events }: { events: CalendarEvent[] }) {
  const descriptions = new Set(events.map((e) => e.description))
  const shared = descriptions.size === 1 ? events[0].description : null
  return (
    <section className="rounded-2xl border border-border/70 bg-card/40 p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-xl">House Hours</h3>
        <p className="text-xs tracking-[0.18em] text-muted-foreground uppercase">Every week</p>
      </div>
      {shared && <Description text={shared} lines={2} className="mt-2 text-sm" />}
      <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {events.map((event) => {
          const over = isOver(event)
          return (
            <li key={event.id}>
              <Link
                to={`/events/${event.slug}`}
                className={cn(
                  "group flex items-center gap-3 rounded-xl border border-border/60 bg-background/40 px-4 py-3 transition-colors",
                  "hover:border-candle/40 hover:bg-accent/60 focus-visible:outline-2 focus-visible:outline-ring",
                  over && "opacity-60",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm">{formatDay(new Date(event.startsAt))}</p>
                  <p className="text-sm text-candle tabular-nums">{formatTimeRange(event.startsAt, event.endsAt)}</p>
                  {!shared && event.description && (
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{event.description}</p>
                  )}
                </div>
                {event.myRsvp && <RsvpBadge status={event.myRsvp.status} />}
                <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function WeekSkeleton() {
  return (
    <div className="space-y-6" aria-busy>
      {[0, 1].map((i) => (
        <div key={i} className="grid gap-3 sm:grid-cols-[4.5rem_minmax(0,1fr)] sm:gap-5">
          <Skeleton className="h-10 w-14" />
          <Skeleton className="h-44 w-full rounded-2xl" />
        </div>
      ))}
    </div>
  )
}
