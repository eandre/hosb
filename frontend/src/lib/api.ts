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
  /** Its date and title, unique: the page is /events/<slug>. */
  slug: string
  title: string
  description: string
  location: string
  startsAt: string
  endsAt: string | null
  capacity: number | null
  /** How many guests a member's shareable link may sign up; null: no limit. */
  shareSignupCap: number | null
  /** null for an event imported from the old calendar. */
  createdBy: string | null
  createdAt: string
  updatedAt: string
  /** Members going, their guests, and guests signed up through links. */
  goingCount: number
  /** Of goingCount: guests signed up through a shareable link. */
  guestCount: number
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

export interface GuestSignup {
  name: string
  /** The member whose link they signed up through. */
  invitedBy: string
  createdAt: string
}

export interface EventDetail extends CalendarEvent {
  attendees: Attendee[]
  guestSignups: GuestSignup[]
}

export interface ShareLink {
  id: number
  token: string
  /** Where it leads, on this origin: /s/<event slug>-<token>. */
  path: string
  kind: "member" | "admin"
  name: string
  eventId: number
  eventSlug: string
  eventTitle: string
  eventStartsAt: string
  createdBy: string
  createdByName: string
  /** Whose invitation an admin's link is to its guests, if not its creator's. */
  invitedBy: string | null
  createdAt: string
  /** How many guests may sign up through it; null: no limit. */
  signupCap: number | null
  /** People who opened it, and how often they did in all. */
  views: number
  totalViews: number
  signups: number
}

/** A shared event, as a guest with the link sees it. */
export interface Shared {
  /** The link's path, with the event's slug as it is now. */
  path: string
  event: {
    slug: string
    title: string
    description: string
    location: string
    startsAt: string
    endsAt: string | null
    placesLeft: number | null
    isOver: boolean
  }
  invitedBy: string
  signupsOpen: boolean
  closedReason: string | null
}

export interface EventInput {
  title: string
  description: string
  location: string
  startsAt: string
  endsAt: string | null
  capacity: number | null
  shareSignupCap: number | null
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

/** The member's Google Calendar sync (backend/google_calendar.py). */
export interface GoogleStatus {
  /** Whether the environment has Google Calendar sync set up. */
  enabled: boolean
  connected: boolean
  googleEmail: string
  /** Where the events go: null until the member picks a calendar. */
  calendarId: string | null
  calendarName: string
  /** "rsvp": what they're going or might go to; "all": every event. */
  mode: "rsvp" | "all"
  /** Google stopped accepting the connection: connect again. */
  needsReconnect: boolean
  lastError: string
  lastSyncedAt: string | null
  syncedEvents: number
}

export interface GoogleCalendar {
  id: string
  name: string
  primary: boolean
}

export type GoogleSettings =
  | { mode: GoogleStatus["mode"]; calendarId: string }
  | { mode: GoogleStatus["mode"]; newCalendar: true }

/** The member's calendar invitations (backend/google_invitations.py). */
export interface InvitationStatus {
  /** Whether the house's Google account is connected to send them. */
  available: boolean
  enabled: boolean
  /** Where theirs go, or would: the address they gave, else their account's
   * (empty if it has none). */
  email: string
  organizerEmail: string
}

/** The house's Google account, which sends the invitations: for admins. */
export interface OrganizerStatus {
  available: boolean
  connected: boolean
  googleEmail: string
  needsReconnect: boolean
  lastError: string
  lastSyncedAt: string | null
  /** Whether Google tells of answers as they're given. */
  push: boolean
  subscribers: number
  events: number
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
  /** An event's detail, by the slug (or id) its page is addressed by. */
  event: (ref: string | number) => ["events", "detail", String(ref)] as const,
  eventLinks: (id: number) => ["events", "links", id] as const,
  adminLinks: ["admin", "links"] as const,
  shared: (token: string) => ["shared", token] as const,
  admin: ["admin"] as const,
  adminStats: ["admin", "stats"] as const,
  adminMembers: ["admin", "members"] as const,
  google: ["google"] as const,
  googleCalendars: ["google", "calendars"] as const,
  invitations: ["invitations"] as const,
  organizer: ["admin", "organizer"] as const,
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

/** An event by its slug, one it had, or its id. */
export function useEvent(ref: string) {
  const api = useApi()
  return useQuery({
    queryKey: keys.event(ref),
    queryFn: () => api<EventDetail>(`/api/events/${encodeURIComponent(ref)}`),
  })
}

/** After a change to an event: the new detail, and every list refetched. */
function useEventChanged() {
  const client = useQueryClient()
  return (event?: EventDetail) => {
    if (event) {
      client.setQueryData(keys.event(event.slug), event)
      client.setQueryData(keys.event(event.id), event)
    }
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

// --- shareable links ---------------------------------------------------------

/** A link's full address, to copy or share. */
export const shareUrl = (link: ShareLink) => `${window.location.origin}${link.path}`

/** A member's one link to the event: the same each time it is asked for. */
export function useMyShareLink(eventId: number) {
  const api = useApi()
  return useMutation({
    mutationFn: () => api<ShareLink>(`/api/events/${eventId}/share-links`, { method: "POST" }),
  })
}

/** An admin's new link to the event, named and capped, and maybe in someone
 * else's name. */
export function useCreateShareLink(eventId: number) {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { name: string; signupCap: number | null; invitedBy: string | null }) =>
      api<ShareLink>(`/api/events/${eventId}/share-links`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.eventLinks(eventId) }),
        client.invalidateQueries({ queryKey: keys.adminLinks }),
      ]),
  })
}

/** The event's links and their numbers: for admins. */
export function useEventShareLinks(eventId: number, enabled: boolean) {
  const api = useApi()
  return useQuery({
    queryKey: keys.eventLinks(eventId),
    queryFn: () =>
      api<{ links: ShareLink[] }>(`/api/events/${eventId}/share-links`).then((r) => r.links),
    enabled,
  })
}

/** Every link and its numbers: for admins. */
export function useAllShareLinks() {
  const api = useApi()
  return useQuery({
    queryKey: keys.adminLinks,
    queryFn: () => api<{ links: ShareLink[] }>("/api/admin/share-links").then((r) => r.links),
  })
}

// What a guest with a link does: no member, no token.

export function useShared(token: string) {
  return useQuery({
    queryKey: keys.shared(token),
    queryFn: () => request<Shared>(`/api/share/${encodeURIComponent(token)}`),
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
  })
}

/** An id for this browser, kept, so that a link's views count people. */
function visitorId(): string {
  const key = "hosb-visitor"
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}

export function recordShareView(token: string): Promise<void> {
  return request<void>(`/api/share/${encodeURIComponent(token)}/views`, {
    method: "POST",
    body: JSON.stringify({ visitorId: visitorId() }),
  })
}

export function useGuestSignup(token: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { name: string; email: string }) =>
      request<{ status: "signed_up" | "already_signed_up"; name: string }>(
        `/api/share/${encodeURIComponent(token)}/signups`,
        { method: "POST", body: JSON.stringify(input) },
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.shared(token) }),
  })
}

export function useGoogleStatus() {
  const api = useApi()
  return useQuery({ queryKey: keys.google, queryFn: () => api<GoogleStatus>("/api/google") })
}

/** The calendars the member can add events to, once they're connected. */
export function useGoogleCalendars(enabled: boolean) {
  const api = useApi()
  return useQuery({
    queryKey: keys.googleCalendars,
    queryFn: () => api<{ calendars: GoogleCalendar[] }>("/api/google/calendars").then((r) => r.calendars),
    enabled,
  })
}

/** Starts connecting: off to Google's sign-in, which sends the member back
 * to /settings. */
export function useConnectGoogle() {
  const api = useApi()
  return useMutation({
    mutationFn: () =>
      api<{ url: string }>("/api/google/connect", {
        method: "POST",
        body: JSON.stringify({ origin: window.location.origin }),
      }),
    onSuccess: ({ url }) => window.location.assign(url),
  })
}

function useGoogleMutation<I>(mutationFn: (input: I) => Promise<GoogleStatus | undefined>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (status) => {
      if (status) client.setQueryData(keys.google, status)
      return client.invalidateQueries({ queryKey: keys.google })
    },
  })
}

/** Which calendar, and which events: then a sync. */
export function useSaveGoogleSettings() {
  const api = useApi()
  return useGoogleMutation((input: GoogleSettings) =>
    api<GoogleStatus>("/api/google/settings", { method: "PUT", body: JSON.stringify(input) }),
  )
}

export function useSyncGoogle() {
  const api = useApi()
  return useGoogleMutation(() => api<GoogleStatus>("/api/google/sync", { method: "POST" }))
}

export function useDisconnectGoogle() {
  const api = useApi()
  return useGoogleMutation(() => api<undefined>("/api/google", { method: "DELETE" }))
}

export function useInvitations() {
  const api = useApi()
  return useQuery({ queryKey: keys.invitations, queryFn: () => api<InvitationStatus>("/api/invitations") })
}

/** Every event as an invitation, at the address given (else the account's),
 * or none. */
export function useSetInvitations() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { enabled: boolean; email?: string }) =>
      api<InvitationStatus>("/api/invitations", { method: "PUT", body: JSON.stringify(input) }),
    onSuccess: (status) => client.setQueryData(keys.invitations, status),
  })
}

export function useOrganizer() {
  const api = useApi()
  return useQuery({ queryKey: keys.organizer, queryFn: () => api<OrganizerStatus>("/api/admin/google-organizer") })
}

/** Starts connecting the house's account: off to Google's sign-in, which
 * sends the admin back to /admin. */
export function useConnectOrganizer() {
  const api = useApi()
  return useMutation({
    mutationFn: () =>
      api<{ url: string }>("/api/admin/google-organizer/connect", {
        method: "POST",
        body: JSON.stringify({ origin: window.location.origin }),
      }),
    onSuccess: ({ url }) => window.location.assign(url),
  })
}

export function useSyncOrganizer() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<OrganizerStatus>("/api/admin/google-organizer/sync", { method: "POST" }),
    onSuccess: (status) => client.setQueryData(keys.organizer, status),
  })
}

export function useDisconnectOrganizer() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<undefined>("/api/admin/google-organizer", { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.organizer }),
  })
}
