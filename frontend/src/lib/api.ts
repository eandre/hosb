import { useAuth } from "@clerk/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback } from "react"

// The backend's types (backend/events.py), as JSON.

export type RSVPStatus = "going" | "maybe" | "not_going"

export interface Me {
  id: string
  name: string
  email: string
  imageUrl: string
  admin: boolean
}

export interface CalendarEvent {
  id: number
  title: string
  description: string
  location: string
  startsAt: string
  endsAt: string | null
  capacity: number | null
  /** null for an event imported from the old calendar. */
  createdBy: string | null
  createdAt: string
  updatedAt: string
  goingCount: number
  maybeCount: number
  myRsvp: { status: RSVPStatus; guests: number } | null
}

export interface Attendee {
  userId: string
  name: string
  imageUrl: string
  status: RSVPStatus
  guests: number
  updatedAt: string
}

export interface EventDetail extends CalendarEvent {
  attendees: Attendee[]
}

export interface EventInput {
  title: string
  description: string
  location: string
  startsAt: string
  endsAt: string | null
  capacity: number | null
}

export interface AdminStats {
  members: number
  activeMembers: number
  upcomingEvents: number
  upcomingGoing: number
}

export interface AdminMember {
  id: string
  name: string
  email: string
  imageUrl: string
  admin: boolean
  joinedAt: string
  lastSeenAt: string
  upcomingGoing: number
  pastGoing: number
}

export const MAX_GUESTS = 4

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** The message of an error response: FastAPI's detail, a string or a list
 * of validation errors. */
function describe(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: { msg?: string }) => (d.msg ?? "invalid").replace(/^Value error, /, ""))
      .join("; ")
  }
  return `request failed (${status})`
}

export async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers)
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (init.body) headers.set("Content-Type", "application/json")
  const response = await fetch(path, { ...init, headers })
  if (response.status === 204) return undefined as T
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, describe(response.status, body))
  return body as T
}

/** A fetch of the API as the signed-in member. */
export function useApi() {
  const { getToken } = useAuth()
  return useCallback(
    async <T,>(path: string, init: RequestInit = {}) => request<T>(path, init, await getToken()),
    [getToken],
  )
}

export const keys = {
  me: ["me"] as const,
  events: ["events"] as const,
  list: (scope: string) => ["events", "list", scope] as const,
  range: (from: string, to: string) => ["events", "range", from, to] as const,
  event: (id: number) => ["events", "detail", id] as const,
  admin: ["admin"] as const,
  adminStats: ["admin", "stats"] as const,
  adminMembers: ["admin", "members"] as const,
}

export function useMe() {
  const api = useApi()
  return useQuery({ queryKey: keys.me, queryFn: () => api<Me>("/api/me"), staleTime: 5 * 60_000 })
}

export function useEvents(scope: "upcoming" | "past") {
  const api = useApi()
  return useQuery({
    queryKey: keys.list(scope),
    queryFn: () => api<{ events: CalendarEvent[] }>(`/api/events?scope=${scope}`).then((r) => r.events),
  })
}

export function useEventsBetween(from: Date, to: Date) {
  const api = useApi()
  const f = from.toISOString()
  const t = to.toISOString()
  return useQuery({
    queryKey: keys.range(f, t),
    queryFn: () =>
      api<{ events: CalendarEvent[] }>(
        `/api/events?from=${encodeURIComponent(f)}&to=${encodeURIComponent(t)}`,
      ).then((r) => r.events),
    placeholderData: (previous) => previous,
  })
}

export function useEvent(id: number) {
  const api = useApi()
  return useQuery({ queryKey: keys.event(id), queryFn: () => api<EventDetail>(`/api/events/${id}`) })
}

/** After a change to an event: the new detail, and every list refetched. */
function useEventChanged() {
  const client = useQueryClient()
  return (event?: EventDetail) => {
    if (event) client.setQueryData(keys.event(event.id), event)
    return Promise.all([
      client.invalidateQueries({ queryKey: keys.events, refetchType: "active" }),
      client.invalidateQueries({ queryKey: keys.admin }),
    ])
  }
}

export function useSaveEvent() {
  const api = useApi()
  const changed = useEventChanged()
  return useMutation({
    mutationFn: ({ id, input }: { id?: number; input: EventInput }) =>
      api<EventDetail>(id ? `/api/events/${id}` : "/api/events", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (event) => changed(event),
  })
}

export function useDeleteEvent() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/api/events/${id}`, { method: "DELETE" }),
    onSuccess: (_, id) => {
      client.removeQueries({ queryKey: keys.event(id) })
      return Promise.all([
        client.invalidateQueries({ queryKey: keys.events }),
        client.invalidateQueries({ queryKey: keys.admin }),
      ])
    },
  })
}

export function useRsvp(id: number) {
  const api = useApi()
  const changed = useEventChanged()
  return useMutation({
    mutationFn: (rsvp: { status: RSVPStatus; guests: number } | null) =>
      api<EventDetail>(`/api/events/${id}/rsvp`, rsvp
        ? { method: "PUT", body: JSON.stringify(rsvp) }
        : { method: "DELETE" }),
    onSuccess: (event) => changed(event),
  })
}

export function useAdminStats() {
  const api = useApi()
  return useQuery({ queryKey: keys.adminStats, queryFn: () => api<AdminStats>("/api/admin/stats") })
}

export function useAdminMembers() {
  const api = useApi()
  return useQuery({
    queryKey: keys.adminMembers,
    queryFn: () => api<{ members: AdminMember[] }>("/api/admin/members").then((r) => r.members),
  })
}

/** Downloads an event's door list: who answered, with emails, as CSV. */
export function useDownloadAttendees() {
  const { getToken } = useAuth()
  return useCallback(
    async (eventId: number) => {
      const response = await fetch(`/api/admin/events/${eventId}/attendees.csv`, {
        headers: { Authorization: `Bearer ${await getToken()}` },
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new ApiError(response.status, describe(response.status, body))
      }
      const filename =
        /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ??
        `event-${eventId}.csv`
      const url = URL.createObjectURL(await response.blob())
      const link = Object.assign(document.createElement("a"), { href: url, download: filename })
      link.click()
      URL.revokeObjectURL(url)
    },
    [getToken],
  )
}
