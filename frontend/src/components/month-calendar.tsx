import { ChevronLeft, ChevronRight } from "lucide-react"
import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { EventListSkeleton, EventRow } from "@/components/event-list"
import { useEventsBetween, type CalendarEvent } from "@/lib/api"
import { dayKey, formatDay, monthGrid, monthName, weekdayNames } from "@/lib/dates"
import { cn } from "@/lib/utils"

/** A month of the calendar: a grid of days with the events on each, and the
 * events of the day picked below it. */
export function MonthCalendar({ onPickDay }: { onPickDay?: (day: Date) => void }) {
  const [month, setMonth] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [picked, setPicked] = useState<Date>(() => new Date())
  const days = useMemo(() => monthGrid(month), [month])
  const { data: events, isPending, error } = useEventsBetween(
    days[0],
    new Date(days[days.length - 1].getFullYear(), days[days.length - 1].getMonth(), days[days.length - 1].getDate() + 1),
  )

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    for (const e of events ?? []) {
      const key = dayKey(new Date(e.startsAt))
      map.set(key, [...(map.get(key) ?? []), e])
    }
    return map
  }, [events])

  const todayKey = dayKey(new Date())
  const pickedEvents = byDay.get(dayKey(picked)) ?? []

  function shift(months: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + months, 1)
    setMonth(next)
    setPicked(next)
  }

  function pick(day: Date) {
    setPicked(day)
    onPickDay?.(day)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
      <div className="rounded-2xl border border-border/70 bg-card/60 p-3 sm:p-4">
        <div className="mb-3 flex items-center justify-between">
          <Button variant="ghost" size="icon" onClick={() => shift(-1)} aria-label="Previous month">
            <ChevronLeft />
          </Button>
          <h2 className="text-lg">{monthName(month)}</h2>
          <Button variant="ghost" size="icon" onClick={() => shift(1)} aria-label="Next month">
            <ChevronRight />
          </Button>
        </div>
        <div className="grid grid-cols-7 text-center text-xs text-muted-foreground">
          {weekdayNames.map((d) => (
            <div key={d} className="pb-2">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {days.map((day) => {
            const key = dayKey(day)
            const dayEvents = byDay.get(key) ?? []
            const inMonth = day.getMonth() === month.getMonth()
            const isPicked = key === dayKey(picked)
            return (
              <button
                key={key}
                type="button"
                onClick={() => pick(day)}
                aria-pressed={isPicked}
                aria-label={`${formatDay(day)}${dayEvents.length ? `, ${dayEvents.length} event(s)` : ""}`}
                className={cn(
                  "flex aspect-square flex-col items-center justify-start gap-1 rounded-lg p-1 text-sm transition-colors sm:aspect-[4/3] md:items-stretch md:p-1.5",
                  inMonth ? "text-foreground" : "text-muted-foreground/40",
                  isPicked ? "bg-accent ring-1 ring-candle/60" : "hover:bg-accent/50",
                )}
              >
                <span
                  className={cn(
                    "grid size-6 place-items-center rounded-full tabular-nums md:self-start",
                    key === todayKey && "bg-candle font-medium text-primary-foreground",
                  )}
                >
                  {day.getDate()}
                </span>
                {/* Dots on phones, titles on wider screens. */}
                <span className="flex gap-0.5 md:hidden">
                  {dayEvents.slice(0, 3).map((e) => (
                    <span key={e.id} className={cn("size-1.5 rounded-full", e.myRsvp?.status === "going" ? "bg-candle" : "bg-foreground/50")} />
                  ))}
                </span>
                <span className="hidden min-w-0 flex-col gap-0.5 md:flex">
                  {dayEvents.slice(0, 2).map((e) => (
                    <span
                      key={e.id}
                      className={cn(
                        "truncate rounded px-1 text-left text-[0.7rem] leading-4",
                        e.myRsvp?.status === "going" ? "bg-candle/25 text-accent-foreground" : "bg-foreground/10",
                      )}
                    >
                      {e.title}
                    </span>
                  ))}
                  {dayEvents.length > 2 && (
                    <span className="px-1 text-left text-[0.7rem] text-muted-foreground">+{dayEvents.length - 2} more</span>
                  )}
                </span>
              </button>
            )
          })}
        </div>
      </div>
      <div>
        <h2 className="mb-3 text-lg">{formatDay(picked)}</h2>
        {error ? (
          <p className="text-sm text-destructive">{error.message}</p>
        ) : isPending ? (
          <EventListSkeleton />
        ) : pickedEvents.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing planned this day.</p>
        ) : (
          <div className="space-y-3">
            {pickedEvents.map((e) => (
              <EventRow key={e.id} event={e} past={new Date(e.endsAt ?? e.startsAt) < new Date()} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
