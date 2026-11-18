import { MailCheck, RefreshCw, TriangleAlert } from "lucide-react"
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  useConnectOrganizer,
  useDisconnectOrganizer,
  useOrganizer,
  useSyncOrganizer,
  type OrganizerStatus,
} from "@/lib/api"
import { ago } from "@/lib/dates"

/** The house's Google account, which sends members their invitations: for
 * admins. */
export function OrganizerCard() {
  const { data: status, isPending, error } = useOrganizer()
  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 sm:p-5">
      <div className="mb-4 flex items-start gap-3">
        <MailCheck className="mt-1 size-5 shrink-0 text-candle" />
        <div>
          <h2 className="text-lg">Calendar invitations</h2>
          <p className="text-sm text-muted-foreground">
            Members who ask for them get every event as an invitation from the house&apos;s Google account, and
            their answers are their RSVPs. Use an account for the house, such as calendar@hosb.se: the events are
            in its calendar, and the invitations come from its address.
          </p>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : isPending ? (
        <Skeleton className="h-16 w-full rounded-xl" />
      ) : !status.available ? (
        <p className="text-sm text-muted-foreground">
          Google isn&apos;t set up here: see the README&apos;s Google Calendar section.
        </p>
      ) : !status.connected ? (
        <ConnectButton>Connect the house&apos;s Google account</ConnectButton>
      ) : (
        <Connected status={status} />
      )}
    </section>
  )
}

function ConnectButton({ children }: { children: string }) {
  const connect = useConnectOrganizer()
  return (
    <Button
      disabled={connect.isPending || connect.isSuccess}
      onClick={() => connect.mutate(undefined, { onError: (err) => toast.error(err.message) })}
    >
      {connect.isPending || connect.isSuccess ? "Off to Google…" : children}
    </Button>
  )
}

function Connected({ status }: { status: OrganizerStatus }) {
  const sync = useSyncOrganizer()
  return (
    <div className="space-y-4">
      {status.needsReconnect && (
        <div className="space-y-3">
          <p className="flex gap-2 rounded-xl border border-ember/40 bg-ember/10 p-3 text-sm">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-ember" />
            <span>Google stopped accepting the house&apos;s account, so no invitations are sent or read.</span>
          </p>
          <ConnectButton>Connect again</ConnectButton>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-background/40 px-3 py-2">
        <p className="min-w-0 text-sm text-muted-foreground">
          {status.subscribers} {status.subscribers === 1 ? "member gets" : "members get"} invitations to{" "}
          {status.events} {status.events === 1 ? "event" : "events"}
          {status.lastSyncedAt && <> · synced {ago(status.lastSyncedAt)}</>}
        </p>
        {!status.needsReconnect && (
          <Button
            variant="ghost"
            size="sm"
            disabled={sync.isPending}
            onClick={() =>
              sync.mutate(undefined, {
                onSuccess: (s) => {
                  if (s.lastError) toast.error(`Syncing failed: ${s.lastError}`)
                  else toast.success("Up to date")
                },
                onError: (err) => toast.error(err.message),
              })
            }
          >
            <RefreshCw className={sync.isPending ? "animate-spin" : undefined} /> Sync now
          </Button>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {status.push
          ? "Google tells the calendar of answers as they're given."
          : "Answers are read every ten minutes, and when you sync: Google can only tell of them as they're given over HTTPS."}
      </p>
      {status.lastError && (
        <p className="text-sm text-destructive" role="alert">
          The last sync failed: {status.lastError}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-4">
        <p className="min-w-0 truncate text-sm text-muted-foreground">
          Sending from <span className="text-foreground">{status.googleEmail || "the house's account"}</span>
        </p>
        <DisconnectButton />
      </div>
    </div>
  )
}

function DisconnectButton() {
  const disconnect = useDisconnectOrganizer()
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="sm" disabled={disconnect.isPending}>
          {disconnect.isPending ? "Disconnecting…" : "Disconnect"}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect the house&apos;s Google account?</AlertDialogTitle>
          <AlertDialogDescription>
            The invitations to events not over are cancelled, and members are emailed that they are. Members who
            asked for invitations get them again once an account is connected.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={() =>
              disconnect.mutate(undefined, {
                onSuccess: () => toast.success("The house's Google account is disconnected"),
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
