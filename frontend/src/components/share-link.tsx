"use client"

import { Check, Copy, Eye, Link2, Share2, UserPlus } from "lucide-react"
import Link from "next/link"
import { useState, type FormEvent } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { ResponsiveModal } from "@/components/responsive-modal"
import {
  shareUrl,
  useCreateShareLink,
  useEventShareLinks,
  useMe,
  useMyShareLink,
  type CalendarEvent,
  type ShareLink,
} from "@/lib/api"
import { formatDay } from "@/lib/dates"

/** The link to copy, or to hand to the device's own sharing. */
function LinkBox({ link, title }: { link: ShareLink; title: string }) {
  const url = shareUrl(link)
  const [copied, setCopied] = useState(false)
  const canShare = typeof navigator !== "undefined" && "share" in navigator

  async function copy() {
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input readOnly value={url} onFocus={(e) => e.target.select()} aria-label="Shareable link" />
        <Button type="button" variant="outline" onClick={copy} aria-label="Copy the link">
          {copied ? <Check /> : <Copy />}
        </Button>
      </div>
      {canShare && (
        <Button
          type="button"
          className="w-full"
          onClick={() => navigator.share({ title, url }).catch(() => undefined)}
        >
          <Share2 /> Share
        </Button>
      )}
      <LinkNumbers link={link} />
    </div>
  )
}

function capLabel(link: ShareLink) {
  return link.signupCap === null ? `${link.signups} signed up` : `${link.signups} of ${link.signupCap} signed up`
}

/** A link's views and sign-ups. */
export function LinkNumbers({ link }: { link: ShareLink }) {
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <span className="flex items-center gap-1" title={`${link.totalViews} views in all`}>
        <Eye className="size-3.5" /> {link.views} {link.views === 1 ? "person" : "people"} viewed it
      </span>
      <span className="flex items-center gap-1">
        <UserPlus className="size-3.5" /> {capLabel(link)}
      </span>
    </p>
  )
}

/** Share the event: a member gets their one link to it, an admin makes a new,
 * named one, saying how many guests may sign up through it. */
export function ShareButton({ event, admin }: { event: CalendarEvent; admin: boolean }) {
  const [open, setOpen] = useState(false)
  const mine = useMyShareLink(event.id)

  function start() {
    setOpen(true)
    if (!admin) mine.mutate(undefined, { onError: (err) => toast.error(err.message) })
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={start}>
        {admin ? (
          <>
            <Link2 /> Share
          </>
        ) : (
          <>
            <UserPlus /> Invite a friend
          </>
        )}
      </Button>
      <ResponsiveModal
        open={open}
        onOpenChange={setOpen}
        title={admin ? "New shareable link" : "Share this event"}
        description={
          admin
            ? "Name the link to tell it apart in the numbers, say how many guests can sign up through it, and whose invitation it is."
            : "Anyone with this link can see this event, and sign up as your guest."
        }
      >
        {admin ? (
          open && <NewLinkForm event={event} onDone={() => setOpen(false)} />
        ) : mine.data ? (
          <div className="pb-2">
            <LinkBox link={mine.data} title={event.title} />
          </div>
        ) : (
          <Skeleton className="mb-2 h-10 w-full" />
        )}
      </ResponsiveModal>
    </>
  )
}

function NewLinkForm({ event, onDone }: { event: CalendarEvent; onDone: () => void }) {
  const create = useCreateShareLink(event.id)
  const firstName = useMe().data?.name.split(" ")[0] ?? ""
  const [name, setName] = useState("")
  const [invitedBy, setInvitedBy] = useState("")
  const [cap, setCap] = useState(event.shareSignupCap?.toString() ?? "")
  const [error, setError] = useState<string | null>(null)

  function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    create.mutate(
      { name, signupCap: cap ? Number(cap) : null, invitedBy: invitedBy.trim() || null },
      { onError: (err) => setError(err.message) },
    )
  }

  if (create.data) {
    return (
      <div className="space-y-4 pb-2">
        <LinkBox link={create.data} title={event.title} />
        <Button type="button" variant="ghost" className="w-full" onClick={onDone}>
          Done
        </Button>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-4 pb-2">
      <div className="grid gap-2">
        <Label htmlFor="link-name">Name</Label>
        <Input
          id="link-name"
          required
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Instagram, the flyer, a partner…"
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="link-cap">Guests who can sign up through it</Label>
        <Input
          id="link-cap"
          type="number"
          inputMode="numeric"
          min={1}
          max={10000}
          value={cap}
          onChange={(e) => setCap(e.target.value)}
          placeholder="No limit"
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="link-invited-by">Invited by</Label>
        <Input
          id="link-invited-by"
          maxLength={100}
          value={invitedBy}
          onChange={(e) => setInvitedBy(e.target.value)}
          placeholder={firstName || "You"}
          aria-describedby="link-invited-by-hint"
        />
        <p id="link-invited-by-hint" className="text-xs text-muted-foreground">
          Making it for someone? Guests will read &ldquo;{invitedBy.trim() || firstName || "You"} invited you
          to&hellip;&rdquo;
        </p>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Making it…" : "Make the link"}
        </Button>
      </div>
    </form>
  )
}

/** A link in a list: whose or what it is, its numbers, and a copy button. */
export function LinkRow({ link, showEvent }: { link: ShareLink; showEvent?: boolean }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    await navigator.clipboard.writeText(shareUrl(link))
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <li className="flex items-start gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">
          {link.kind === "admin" ? link.name : `${link.createdByName || "A member"}'s link`}
          {link.invitedBy && <span className="font-normal text-muted-foreground"> · for {link.invitedBy}</span>}
        </p>
        <p className="mb-1 truncate text-xs text-muted-foreground">
          {showEvent ? (
            <Link href={`/events/${link.eventSlug}`} className="hover:text-foreground hover:underline">
              {link.eventTitle} · {formatDay(new Date(link.eventStartsAt))}
            </Link>
          ) : link.kind === "admin" ? (
            `by ${link.createdByName || "an admin"}`
          ) : (
            "a member's link"
          )}
        </p>
        <LinkNumbers link={link} />
      </div>
      <Button variant="ghost" size="icon" onClick={copy} aria-label="Copy the link">
        {copied ? <Check /> : <Copy />}
      </Button>
    </li>
  )
}

/** The event's links and their numbers: for admins. */
export function ShareLinksPanel({ event }: { event: CalendarEvent }) {
  const { data: links, isPending, error } = useEventShareLinks(event.id, true)
  return (
    <section>
      <h3 className="mb-1 text-sm font-sans font-medium text-muted-foreground">Shareable links</h3>
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : isPending ? (
        <Skeleton className="h-14 w-full rounded-lg" />
      ) : links.length === 0 ? (
        <p className="text-sm text-muted-foreground">None yet. Share makes one.</p>
      ) : (
        <ul className="divide-y divide-border/70">
          {links.map((link) => (
            <LinkRow key={link.id} link={link} />
          ))}
        </ul>
      )}
    </section>
  )
}
