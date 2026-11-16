// Dates as the house writes them: in the member's own time zone (Stockholm,
// for nearly everyone), with the week starting on Monday.

const locale = "en-GB"

export const dayKey = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`

export const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })

export const formatDay = (d: Date) => {
  const today = new Date()
  const tomorrow = new Date()
  tomorrow.setDate(today.getDate() + 1)
  if (dayKey(d) === dayKey(today)) return "Today"
  if (dayKey(d) === dayKey(tomorrow)) return "Tomorrow"
  return d.toLocaleDateString(locale, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: d.getFullYear() === today.getFullYear() ? undefined : "numeric",
  })
}

export const formatLongDate = (iso: string) =>
  new Date(iso).toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })

export const formatTimeRange = (startsAt: string, endsAt: string | null) =>
  endsAt ? `${formatTime(startsAt)}–${formatTime(endsAt)}` : formatTime(startsAt)

export const monthName = (d: Date) => d.toLocaleDateString(locale, { month: "long", year: "numeric" })

export const weekdayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

/** The days of the weeks that hold the month of d, Monday first. */
export function monthGrid(d: Date): Date[] {
  const first = new Date(d.getFullYear(), d.getMonth(), 1)
  const start = new Date(first)
  start.setDate(1 - ((first.getDay() + 6) % 7))
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  const days: Date[] = []
  for (const day = new Date(start); day <= last || days.length % 7 !== 0; day.setDate(day.getDate() + 1)) {
    days.push(new Date(day))
  }
  return days
}

/** "2026-11-16" and "19:30" as written in a form, to the instant they are here. */
export function toInstant(date: string, time: string): string {
  const [y, m, d] = date.split("-").map(Number)
  const [hh, mm] = time.split(":").map(Number)
  return new Date(y, m - 1, d, hh, mm).toISOString()
}

/** The form's date and time of an instant. */
export function fromInstant(iso: string): { date: string; time: string } {
  const d = new Date(iso)
  return {
    date: dayKey(d),
    time: `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
  }
}

export function groupByDay<T extends { startsAt: string }>(items: T[]): { day: Date; items: T[] }[] {
  const groups = new Map<string, { day: Date; items: T[] }>()
  for (const item of items) {
    const day = new Date(item.startsAt)
    const key = dayKey(day)
    if (!groups.has(key)) groups.set(key, { day, items: [] })
    groups.get(key)!.items.push(item)
  }
  return [...groups.values()]
}
