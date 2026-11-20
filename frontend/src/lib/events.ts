import type { CalendarEvent, RSVPStatus } from "@/lib/api"

export const statusLabel: Record<RSVPStatus, string> = {
  going: "Going",
  maybe: "Maybe",
  not_going: "Can't go",
}

/** Places left for members and guests, or null without a limit. */
export function placesLeft(event: CalendarEvent): number | null {
  return event.capacity === null ? null : Math.max(event.capacity - event.goingCount, 0)
}

const DEFAULT_DURATION_MS = 3 * 60 * 60 * 1000

/** Whether the event is over: an event without an end lasts three hours,
 * as the backend has it. */
export function isOver(event: CalendarEvent): boolean {
  const end = event.endsAt ? new Date(event.endsAt) : new Date(new Date(event.startsAt).getTime() + DEFAULT_DURATION_MS)
  return end < new Date()
}
