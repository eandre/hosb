import { useUser } from "@clerk/react"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EventFormModal } from "@/components/event-form"
import { EventList, EventListSkeleton } from "@/components/event-list"
import { MonthCalendar } from "@/components/month-calendar"
import { WeekView } from "@/components/week-view"
import { useEvents, useMe } from "@/lib/api"
import { parseDay } from "@/lib/dates"
import { views, type View } from "@/lib/views"

function Upcoming() {
  const { data, isPending, error } = useEvents("upcoming")
  if (error) return <p className="py-8 text-destructive">{error.message}</p>
  if (isPending) return <EventListSkeleton />
  return <EventList events={data} empty="Nothing is planned yet. Check back soon." />
}

function Past() {
  const { data, isPending, error } = useEvents("past")
  if (error) return <p className="py-8 text-destructive">{error.message}</p>
  if (isPending) return <EventListSkeleton />
  return <EventList events={data} past empty="No past events." />
}

export function EventsPage() {
  const { user } = useUser()
  const { data: me } = useMe()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const [creating, setCreating] = useState(false)
  const view = (Object.keys(views) as View[]).find((v) => views[v] === pathname) ?? "upcoming"
  // A new event is on the day picked in the calendar, if one is.
  const day = view === "calendar" ? (parseDay(params.get("date")) ?? undefined) : undefined

  return (
    <div>
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">
            {user?.firstName ? `Welcome, ${user.firstName}` : "Welcome"}
          </p>
          <h1 className="text-3xl sm:text-4xl">At the house</h1>
        </div>
        {me?.admin && (
          <Button className="hidden md:inline-flex" onClick={() => setCreating(true)}>
            <Plus /> New event
          </Button>
        )}
      </div>

      <Tabs value={view} onValueChange={(v) => navigate(views[v as View])}>
        <TabsList className="mb-5 w-full sm:w-auto">
          <TabsTrigger value="upcoming" className="flex-1 sm:flex-none">Upcoming</TabsTrigger>
          <TabsTrigger value="week" className="flex-1 sm:flex-none">Week</TabsTrigger>
          <TabsTrigger value="calendar" className="flex-1 sm:flex-none">Calendar</TabsTrigger>
          <TabsTrigger value="past" className="flex-1 sm:flex-none">Past</TabsTrigger>
        </TabsList>
        <TabsContent value="upcoming">
          <Upcoming />
        </TabsContent>
        <TabsContent value="week">
          <WeekView />
        </TabsContent>
        <TabsContent value="calendar">
          <MonthCalendar />
        </TabsContent>
        <TabsContent value="past">
          <Past />
        </TabsContent>
      </Tabs>

      {me?.admin && (
        <>
          {/* On phones, within thumb's reach. */}
          <Button
            size="icon-lg"
            className="fixed right-5 bottom-[max(1.25rem,env(safe-area-inset-bottom))] z-20 size-14 rounded-full shadow-lg shadow-black/40 md:hidden"
            onClick={() => setCreating(true)}
            aria-label="New event"
          >
            <Plus className="size-6" />
          </Button>
          <EventFormModal
            open={creating}
            onOpenChange={setCreating}
            date={day}
            onSaved={(event) => navigate(`/events/${event.slug}`)}
          />
        </>
      )}
    </div>
  )
}
