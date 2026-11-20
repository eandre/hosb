import { CalendarSync, MailCheck, RefreshCw, TriangleAlert } from "lucide-react"
import { useState, type FormEvent } from "react"
import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  useConnectGoogle,
  useDisconnectGoogle,
  useGoogleCalendars,
  useGoogleStatus,
  useInvitations,
  useSetInvitations,
  useSaveGoogleSettings,
  useSyncGoogle,
  type GoogleStatus,
} from "@/lib/api"
import { ago } from "@/lib/dates"
import { useGoogleResult } from "@/lib/google-result"
import { AddEmail } from "@/components/add-email"
import { LegalLinks } from "@/components/site-footer"

// The calendar option that makes a calendar of its own for the events.
const NEW_CALENDAR = "new"

export function SettingsPage() {
  useGoogleResult("/settings")
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-3xl leading-tight">Settings</h1>
      <InvitationsSection />
      <GoogleCalendarSection />
      <p className="text-xs text-muted-foreground md:hidden">
        <LegalLinks />
      </p>
    </div>
  )
}

/** Every event as an invitation in the member's calendar, answered there. */
function InvitationsSection() {
  const { data: status, isPending, error } = useInvitations()
  const google = useGoogleStatus().data
  const set = useSetInvitations()

  function toggle(enabled: boolean) {
    set.mutate(enabled, {
      onSuccess: () =>
        toast.success(enabled ? "Invitations are on their way" : "No more invitations: the ones sent are cancelled"),
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 sm:p-5">
      <div className="mb-4 flex items-start gap-3">
        <MailCheck className="mt-1 size-5 shrink-0 text-candle" />
        <div>
          <h2 className="text-lg">Calendar invitations</h2>
          <p className="text-sm text-muted-foreground">
            Get every event as an invitation in your calendar. Answer yes, maybe or no there, and it&apos;s your
            RSVP here.
          </p>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : isPending ? (
        <Skeleton className="h-16 w-full rounded-xl" />
      ) : !status.available && !status.enabled ? (
        <p className="text-sm text-muted-foreground">Invitations aren&apos;t set up here yet.</p>
      ) : !status.email && !status.enabled ? (
        <AddEmail onAdded={() => toggle(true)} />
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {status.enabled ? "They go to " : "They'd go to "}
            <span className="text-foreground">{status.email}</span>
            {status.organizerEmail && (
              <>
                , from <span className="text-foreground">{status.organizerEmail}</span>
              </>
            )}
            .
          </p>
          {status.enabled && !status.available && (
            <p className="text-sm text-ember">The house&apos;s calendar isn&apos;t connected right now, so none are sent.</p>
          )}
          {status.enabled && google?.connected && google.mode === "all" && (
            <p className="text-sm text-muted-foreground">
              Your Google Calendar below gets every event too, so you&apos;ll see them twice there.
            </p>
          )}
          <Button
            variant={status.enabled ? "ghost" : "default"}
            disabled={set.isPending}
            onClick={() => toggle(!status.enabled)}
          >
            {set.isPending ? "Saving…" : status.enabled ? "Stop sending me invitations" : "Send me invitations"}
          </Button>
        </div>
      )}
    </section>
  )
}

function GoogleCalendarSection() {
  const { data: status, isPending, error } = useGoogleStatus()
  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 sm:p-5">
      <div className="mb-4 flex items-start gap-3">
        <CalendarSync className="mt-1 size-5 shrink-0 text-candle" />
        <div>
          <h2 className="text-lg">Google Calendar</h2>
          <p className="text-sm text-muted-foreground">
            Have the house&apos;s events in your Google Calendar, kept up to date as they change.
          </p>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : isPending ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : !status.connected ? (
        status.enabled ? (
          <ConnectButton>Connect Google Calendar</ConnectButton>
        ) : (
          <p className="text-sm text-muted-foreground">Google Calendar sync isn&apos;t set up here yet.</p>
        )
      ) : status.needsReconnect ? (
        <div className="space-y-4">
          <p className="flex gap-2 rounded-xl border border-ember/40 bg-ember/10 p-3 text-sm">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-ember" />
            <span>
              Google stopped accepting the connection, so {status.calendarName || "your calendar"} isn&apos;t
              being kept up to date. Connect again to carry on.
            </span>
          </p>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <ConnectButton>Connect again</ConnectButton>
            <DisconnectButton status={status} />
          </div>
        </div>
      ) : (
        <Connected status={status} />
      )}
    </section>
  )
}

function ConnectButton({ children }: { children: string }) {
  const connect = useConnectGoogle()
  return (
    <Button
      disabled={connect.isPending || connect.isSuccess}
      onClick={() => connect.mutate(undefined, { onError: (err) => toast.error(err.message) })}
    >
      {connect.isPending || connect.isSuccess ? "Off to Google…" : children}
    </Button>
  )
}

function Connected({ status }: { status: GoogleStatus }) {
  const calendars = useGoogleCalendars(true)
  const save = useSaveGoogleSettings()
  const sync = useSyncGoogle()
  const [mode, setMode] = useState(status.mode)
  // A calendar of its own, unless they've picked one.
  const [calendar, setCalendar] = useState(status.calendarId ?? NEW_CALENDAR)
  const changed = status.calendarId === null || mode !== status.mode || calendar !== status.calendarId

  function submit(e: FormEvent) {
    e.preventDefault()
    const input =
      calendar === NEW_CALENDAR ? { mode, newCalendar: true as const } : { mode, calendarId: calendar }
    save.mutate(input, {
      onSuccess: (saved) => {
        if (!saved) return
        setCalendar(saved.calendarId ?? NEW_CALENDAR)
        if (saved.lastError) toast.error(`Saved, but syncing failed: ${saved.lastError}`)
        else toast.success(`${saved.syncedEvents} ${saved.syncedEvents === 1 ? "event" : "events"} in ${saved.calendarName}`)
      },
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <div className="space-y-5">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-2">
          <Label id="google-mode">Which events</Label>
          <ToggleGroup
            type="single"
            variant="outline"
            spacing={0}
            className="w-full"
            aria-labelledby="google-mode"
            value={mode}
            onValueChange={(value) => {
              if (value) setMode(value as GoogleStatus["mode"])
            }}
          >
            <ToggleGroupItem
              value="rsvp"
              className="flex-1 data-[state=on]:bg-candle data-[state=on]:text-primary-foreground"
            >
              The ones I&apos;m going to
            </ToggleGroupItem>
            <ToggleGroupItem
              value="all"
              className="flex-1 data-[state=on]:bg-candle data-[state=on]:text-primary-foreground"
            >
              All events
            </ToggleGroupItem>
          </ToggleGroup>
          <p className="text-xs text-muted-foreground">
            {mode === "rsvp"
              ? "Events you've said you're going to, or might go to."
              : "Every event, with the ones you're going to shown as busy."}
          </p>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="google-calendar">Calendar</Label>
          {calendars.error ? (
            <p className="text-sm text-destructive">{calendars.error.message}</p>
          ) : calendars.isPending ? (
            <Skeleton className="h-9 w-full rounded-lg" />
          ) : (
            <select
              id="google-calendar"
              value={calendar}
              onChange={(e) => setCalendar(e.target.value)}
              className="h-9 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm dark:bg-input/30"
            >
              <option value={NEW_CALENDAR}>A new calendar: House of Soft Beasts</option>
              {calendars.data.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.primary ? " (your own)" : ""}
                </option>
              ))}
            </select>
          )}
        </div>
        {changed && (
          <Button type="submit" disabled={save.isPending || calendars.isPending}>
            {save.isPending ? "Syncing…" : status.calendarId ? "Save and sync" : "Start syncing"}
          </Button>
        )}
      </form>

      {status.calendarId && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-background/40 px-3 py-2">
          <p className="min-w-0 text-sm text-muted-foreground">
            {status.syncedEvents} {status.syncedEvents === 1 ? "event" : "events"} in{" "}
            <span className="text-foreground">{status.calendarName}</span>
            {status.lastSyncedAt && <> · synced {ago(status.lastSyncedAt)}</>}
          </p>
          <Button
            variant="ghost"
            size="sm"
            disabled={sync.isPending}
            onClick={() =>
              sync.mutate(undefined, {
                onSuccess: (s) => {
                  if (s?.lastError) toast.error(`Syncing failed: ${s.lastError}`)
                  else toast.success("Up to date")
                },
                onError: (err) => toast.error(err.message),
              })
            }
          >
            <RefreshCw className={sync.isPending ? "animate-spin" : undefined} /> Sync now
          </Button>
        </div>
      )}
      {status.lastError && (
        <p className="text-sm text-destructive" role="alert">
          The last sync failed: {status.lastError}. It&apos;s tried again within the hour.
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-4">
        <p className="min-w-0 truncate text-sm text-muted-foreground">
          Connected as <span className="text-foreground">{status.googleEmail || "your Google account"}</span>
        </p>
        <DisconnectButton status={status} />
      </div>
    </div>
  )
}

function DisconnectButton({ status }: { status: GoogleStatus }) {
  const disconnect = useDisconnectGoogle()
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="sm" disabled={disconnect.isPending}>
          {disconnect.isPending ? "Disconnecting…" : "Disconnect"}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect Google Calendar?</AlertDialogTitle>
          <AlertDialogDescription>
            {status.calendarName
              ? `The house's events are taken out of ${status.calendarName}, and it stops getting updates.`
              : "The calendar stops getting the house's events."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={() =>
              disconnect.mutate(undefined, {
                onSuccess: () => toast.success("Google Calendar disconnected"),
                onError: (err) => toast.error(err.message),
              })
            }
          >
            Disconnect
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
