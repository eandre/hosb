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
