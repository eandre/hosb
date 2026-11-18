import {
  CalendarDays,
  Download,
  ExternalLink,
  Link2,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
  Users,
} from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { DeleteEventDialog } from "@/components/delete-event-dialog"
import { EventFormModal } from "@/components/event-form"
import { LinkRow } from "@/components/share-link"
import {
  useAdminMembers,
  useAdminStats,
  useAllShareLinks,
  useDownloadAttendees,
  useEvents,
  useMe,
  type AdminMember,
  type CalendarEvent,
} from "@/lib/api"
import { ago, formatTimeRange } from "@/lib/dates"
import { placesLeft } from "@/lib/events"
import { cn } from "@/lib/utils"

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]!.toUpperCase())
      .join("") || "?"
  )
}

export function AdminPage() {
  const { data: me, isPending } = useMe()
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  if (isPending) return <Skeleton className="h-10 w-48" />
  if (!me?.admin) {
    return (
      <div className="py-16 text-center">
        <p className="text-muted-foreground">This page is for the house's admins.</p>
        <Button asChild variant="link" className="mt-2">
          <Link to="/">Back to the calendar</Link>
        </Button>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Admin</p>
          <h1 className="text-3xl sm:text-4xl">The house at a glance</h1>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus /> <span className="sr-only sm:not-sr-only">New event</span>
        </Button>
      </div>

      <Stats />

      <Tabs defaultValue="events" className="mt-8">
        <TabsList className="mb-5 w-full sm:w-auto">
          <TabsTrigger value="events" className="flex-1 sm:flex-none">
            <CalendarDays /> Events
          </TabsTrigger>
          <TabsTrigger value="members" className="flex-1 sm:flex-none">
            <Users /> Members
          </TabsTrigger>
          <TabsTrigger value="links" className="flex-1 sm:flex-none">
            <Link2 /> Links
          </TabsTrigger>
        </TabsList>
        <TabsContent value="events">
          <EventsTab />
        </TabsContent>
        <TabsContent value="members">
          <MembersTab />
        </TabsContent>
        <TabsContent value="links">
          <LinksTab />
        </TabsContent>
      </Tabs>

      <EventFormModal
        open={creating}
        onOpenChange={setCreating}
        onSaved={(event) => navigate(`/events/${event.slug}`)}
      />
    </div>
  )
}

function Stat({ label, value, hint }: { label: string; value: ReactNode; hint: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-card/70 p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-3xl tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  )
}

function Stats() {
  const { data, error } = useAdminStats()
  if (error) return <p className="text-sm text-destructive">{error.message}</p>
  const value = (n?: number) => (n === undefined ? <Skeleton className="h-9 w-12" /> : n)
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat label="Members" value={value(data?.members)} hint="who have signed in" />
      <Stat label="Active" value={value(data?.activeMembers)} hint="seen in the last 30 days" />
      <Stat label="Upcoming events" value={value(data?.upcomingEvents)} hint="not yet over" />
      <Stat label="Coming" value={value(data?.upcomingGoing)} hint="to upcoming events, with guests" />
    </div>
  )
}

function EventsTab() {
  const [scope, setScope] = useState<"upcoming" | "past">("upcoming")
  const { data, isPending, error } = useEvents(scope)

  return (
    <div>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={0}
        value={scope}
        onValueChange={(v) => v && setScope(v as "upcoming" | "past")}
        className="mb-4"
      >
        <ToggleGroupItem value="upcoming">Upcoming</ToggleGroupItem>
        <ToggleGroupItem value="past">Past</ToggleGroupItem>
      </ToggleGroup>
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : isPending ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : data.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          {scope === "upcoming" ? "Nothing planned yet." : "No past events."}
        </p>
      ) : (
        <ul className="space-y-3">
          {data.map((event) => (
            <AdminEventRow key={event.id} event={event} />
          ))}
        </ul>
      )}
    </div>
  )
}

function AdminEventRow({ event }: { event: CalendarEvent }) {
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const download = useDownloadAttendees()
  const start = new Date(event.startsAt)
  const left = placesLeft(event)
  const fill = event.capacity ? Math.min(event.goingCount / event.capacity, 1) : null

  return (
    <li className="flex items-center gap-4 rounded-xl border border-border/70 bg-card/70 p-3 sm:p-4">
      <div className="flex w-12 shrink-0 flex-col items-center rounded-lg bg-accent py-1.5 text-center">
        <span className="text-xs uppercase text-muted-foreground">
          {start.toLocaleDateString("en-GB", { month: "short" })}
        </span>
        <span className="font-heading text-xl leading-6 tabular-nums">{start.getDate()}</span>
      </div>
      <div className="min-w-0 flex-1">
        <Link to={`/events/${event.slug}`} className="block truncate text-base font-medium hover:underline">
          {event.title}
        </Link>
        <p className="text-sm text-muted-foreground tabular-nums">
          {start.toLocaleDateString("en-GB", { weekday: "short" })} {formatTimeRange(event.startsAt, event.endsAt)}
          {event.location && <span className="hidden sm:inline"> · {event.location}</span>}
        </p>
        <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
          {fill !== null && (
            <div
              className="h-1.5 w-20 overflow-hidden rounded-full bg-foreground/10 sm:w-32"
              role="progressbar"
              aria-valuenow={event.goingCount}
              aria-valuemax={event.capacity ?? undefined}
              aria-label="Places taken"
            >
              <div className={cn("h-full rounded-full", left === 0 ? "bg-ember" : "bg-candle")} style={{ width: `${fill * 100}%` }} />
            </div>
          )}
          <span className="tabular-nums">
            {event.goingCount}
            {event.capacity !== null && ` / ${event.capacity}`} going
            {event.maybeCount > 0 && ` · ${event.maybeCount} maybe`}
          </span>
        </div>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Actions for ${event.title}`}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setEditing(true)}>
            <Pencil /> Edit
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => download(event.id).catch((err: Error) => toast.error(err.message))}
          >
            <Download /> Door list (CSV)
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(true)}>
            <Trash2 /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <EventFormModal open={editing} onOpenChange={setEditing} event={event} />
      <DeleteEventDialog event={event} open={deleting} onOpenChange={setDeleting} />
    </li>
  )
}

function MembersTab() {
  const { data, isPending, error } = useAdminMembers()
  const [query, setQuery] = useState("")
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!data || !q) return data
    return data.filter((m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q))
  }, [data, query])

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search by name or email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
            aria-label="Search members"
          />
        </div>
        <a
          href="https://dashboard.clerk.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Admins are made in Clerk: public metadata {'{"admin": true}'} <ExternalLink className="size-3" />
        </a>
      </div>
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : isPending ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : shown!.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          {query ? "No one matches." : "No one has signed in yet."}
        </p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/70 bg-card/70">
          <div className="hidden grid-cols-[minmax(0,1fr)_8rem_8rem_8rem] gap-4 border-b border-border/70 px-4 py-2 text-xs text-muted-foreground md:grid">
            <span>Member</span>
            <span>Last seen</span>
            <span>Joined</span>
            <span className="text-right">Going: next / past</span>
          </div>
          <ul className="divide-y divide-border/70">
            {shown!.map((m) => (
              <MemberRow key={m.id} member={m} />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function MemberRow({ member: m }: { member: AdminMember }) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3 md:grid-cols-[minmax(0,1fr)_8rem_8rem_8rem]">
      <div className="flex min-w-0 items-center gap-3">
        <Avatar className="size-9">
          <AvatarImage src={m.imageUrl || undefined} alt="" />
          <AvatarFallback className="text-xs">{initials(m.name)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="flex items-center gap-2 truncate text-sm font-medium">
            <span className="truncate">{m.name || "Unnamed member"}</span>
            {m.admin && (
              <Badge variant="secondary" className="shrink-0">
                Admin
              </Badge>
            )}
          </p>
          <p className="truncate text-xs text-muted-foreground">{m.email || m.id}</p>
        </div>
      </div>
      <span className="text-sm text-muted-foreground md:order-none">
        <span className="md:hidden">Seen </span>
        {ago(m.lastSeenAt)}
      </span>
      <span className="col-span-2 text-xs text-muted-foreground md:col-span-1 md:text-sm">
        <span className="md:hidden">Joined </span>
        {new Date(m.joinedAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
        <span className="md:hidden">
          {" · "}
          {m.upcomingGoing} upcoming, {m.pastGoing} attended
        </span>
      </span>
      <span
        className="hidden text-right text-sm tabular-nums md:block"
        title={`${m.upcomingGoing} upcoming, ${m.pastGoing} attended`}
      >
        {m.upcomingGoing} <span className="text-muted-foreground">/ {m.pastGoing}</span>
      </span>
    </li>
  )
}

/** Every shareable link, the latest events' first, with its views and
 * sign-ups. */
function LinksTab() {
  const { data: links, isPending, error } = useAllShareLinks()
  const totals = useMemo(
    () =>
      (links ?? []).reduce(
        (t, l) => ({ views: t.views + l.views, signups: t.signups + l.signups }),
        { views: 0, signups: 0 },
      ),
    [links],
  )
  if (error) return <p className="text-sm text-destructive">{error.message}</p>
  if (isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl" />
        ))}
      </div>
    )
  }
  if (links.length === 0) {
    return (
      <p className="py-12 text-center text-muted-foreground">
        No shareable links yet. Share, on an event&apos;s page, makes one.
      </p>
    )
  }
  return (
    <div>
      <p className="mb-3 text-sm text-muted-foreground">
        {links.length} {links.length === 1 ? "link" : "links"} · {totals.views} people viewed them ·{" "}
        {totals.signups} guests signed up
      </p>
      <ul className="divide-y divide-border/70 rounded-xl border border-border/70 bg-card/70 px-4">
        {links.map((link) => (
          <LinkRow key={link.id} link={link} showEvent />
        ))}
      </ul>
    </div>
  )
}
