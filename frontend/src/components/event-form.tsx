import { useState, type FormEvent } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ResponsiveModal } from "@/components/responsive-modal"
import { useSaveEvent, type CalendarEvent, type EventDetail } from "@/lib/api"
import { dayKey, fromInstant, toInstant } from "@/lib/dates"

interface Fields {
  title: string
  date: string
  start: string
  end: string
  location: string
  capacity: string
  shareSignupCap: string
  description: string
}

function initial(event?: CalendarEvent, date?: Date): Fields {
  if (!event) {
    return {
      title: "",
      date: dayKey(date ?? new Date()),
      start: "19:00",
      end: "22:00",
      location: "",
      capacity: "",
      shareSignupCap: "",
      description: "",
    }
  }
  const start = fromInstant(event.startsAt)
  return {
    title: event.title,
    date: start.date,
    start: start.time,
    end: event.endsAt ? fromInstant(event.endsAt).time : "",
    location: event.location,
    capacity: event.capacity?.toString() ?? "",
    shareSignupCap: event.shareSignupCap?.toString() ?? "",
    description: event.description,
  }
}

/** Create an event, or change one: for admins. */
export function EventFormModal({
  open,
  onOpenChange,
  event,
  date,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  event?: CalendarEvent
  date?: Date
  onSaved?: (event: EventDetail) => void
}) {
  return (
    <ResponsiveModal
      open={open}
      onOpenChange={onOpenChange}
      title={event ? "Edit event" : "New event"}
      description={event ? undefined : "Members will see it in the calendar right away."}
    >
      {/* Remount on open, so the form starts from the event as it is now. */}
      {open && (
        <EventForm
          event={event}
          date={date}
          onCancel={() => onOpenChange(false)}
          onSaved={(saved) => {
            onOpenChange(false)
            onSaved?.(saved)
          }}
        />
      )}
    </ResponsiveModal>
  )
}

function EventForm({
  event,
  date,
  onCancel,
  onSaved,
}: {
  event?: CalendarEvent
  date?: Date
  onCancel: () => void
  onSaved: (event: EventDetail) => void
}) {
  const [fields, setFields] = useState(() => initial(event, date))
  const [error, setError] = useState<string | null>(null)
  const save = useSaveEvent()

  const set = (key: keyof Fields) => (e: { target: { value: string } }) =>
    setFields((f) => ({ ...f, [key]: e.target.value }))

  function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const startsAt = toInstant(fields.date, fields.start)
    let endsAt: string | null = null
    if (fields.end) {
      // An end before the start is past midnight, the next day.
      const end = new Date(toInstant(fields.date, fields.end))
      if (end <= new Date(startsAt)) end.setDate(end.getDate() + 1)
      endsAt = end.toISOString()
    }
    save.mutate(
      {
        id: event?.id,
        input: {
          title: fields.title,
          description: fields.description,
          location: fields.location,
          startsAt,
          endsAt,
          capacity: fields.capacity ? Number(fields.capacity) : null,
          shareSignupCap: fields.shareSignupCap ? Number(fields.shareSignupCap) : null,
        },
      },
      {
        onSuccess: (saved) => {
          toast.success(event ? "Event updated" : "Event created")
          onSaved(saved)
        },
        onError: (err) => setError(err.message),
      },
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-4 pb-2">
      <div className="grid gap-2">
        <Label htmlFor="title">Title</Label>
        <Input id="title" required maxLength={200} value={fields.title} onChange={set("title")} placeholder="House Dinner" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="grid gap-2">
          <Label htmlFor="date">Date</Label>
          <Input id="date" type="date" required value={fields.date} onChange={set("date")} />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:col-span-2">
          <div className="grid gap-2">
            <Label htmlFor="start">Starts</Label>
            <Input id="start" type="time" required value={fields.start} onChange={set("start")} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="end">Ends</Label>
            <Input id="end" type="time" value={fields.end} onChange={set("end")} />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-[1fr_7rem] gap-4">
        <div className="grid gap-2">
          <Label htmlFor="location">Where</Label>
          <Input id="location" maxLength={200} value={fields.location} onChange={set("location")} placeholder="The long table" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="capacity">Places</Label>
          <Input
            id="capacity"
            type="number"
            inputMode="numeric"
            min={1}
            max={10000}
            value={fields.capacity}
            onChange={set("capacity")}
            placeholder="No limit"
          />
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="description">About</Label>
        <Textarea
          id="description"
          rows={5}
          maxLength={5000}
          value={fields.description}
          onChange={set("description")}
          placeholder="What will happen, what to bring…"
        />
      </div>
      <div className="grid grid-cols-[1fr_7rem] items-end gap-4">
        <div>
          <Label htmlFor="shareSignupCap">Guests per member link</Label>
          <p className="mt-1 text-xs text-muted-foreground">
            How many guests can sign up through each member&apos;s shareable link.
          </p>
        </div>
        <Input
          id="shareSignupCap"
          type="number"
          inputMode="numeric"
          min={1}
          max={10000}
          value={fields.shareSignupCap}
          onChange={set("shareSignupCap")}
          placeholder="No limit"
        />
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : event ? "Save changes" : "Create event"}
        </Button>
      </div>
    </form>
  )
}
