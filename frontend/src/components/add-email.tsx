import { useAuth, useUser } from "@clerk/react"
import { useQueryClient } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { keys } from "@/lib/api"

type User = NonNullable<ReturnType<typeof useUser>["user"]>
type EmailAddress = User["emailAddresses"][number]

/** Clerk's own account of what went wrong, as it says it. */
function clerkMessage(err: unknown): string {
  const first = (err as { errors?: { longMessage?: string; message?: string }[] } | null)?.errors?.[0]
  return first?.longMessage ?? first?.message ?? (err instanceof Error ? err.message : "That didn't work. Try again.")
}

/** Adds an email address to the member's account (their Clerk profile),
 * verified with a code Clerk emails them, and makes it their primary
 * address: the one their session token, and so the calendar, has for them. */
export function AddEmail({ onAdded }: { onAdded: () => void }) {
  const { user } = useUser()
  const { getToken } = useAuth()
  const client = useQueryClient()
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [sentTo, setSentTo] = useState<EmailAddress | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!user) return null
  const signedInUser = user
  // An address they have verified already, but that isn't their primary one.
  const verified = signedInUser.emailAddresses.find((a) => a.verification.status === "verified")

  async function attempt(work: () => Promise<void>) {
    setError(null)
    setBusy(true)
    try {
      await work()
    } catch (err) {
      setError(clerkMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function makePrimary(id: string) {
    await signedInUser.update({ primaryEmailAddressId: id })
    // The session token says who the member is: a fresh one has the address.
    await getToken({ skipCache: true })
    await client.invalidateQueries({ queryKey: keys.invitations })
    await client.invalidateQueries({ queryKey: keys.me })
    onAdded()
  }

  function sendCode(e: FormEvent) {
    e.preventDefault()
    void attempt(async () => {
      const wanted = email.trim()
      const address =
        signedInUser.emailAddresses.find((a) => a.emailAddress.toLowerCase() === wanted.toLowerCase()) ??
        (await signedInUser.createEmailAddress({ email: wanted }))
      if (address.verification.status === "verified") {
        await makePrimary(address.id)
        return
      }
      await address.prepareVerification({ strategy: "email_code" })
      setSentTo(address)
      setCode("")
    })
  }

  function checkCode(e: FormEvent) {
    e.preventDefault()
    if (!sentTo) return
    void attempt(async () => {
      const checked = await sentTo.attemptVerification({ code: code.trim() })
      if (checked.verification.status !== "verified") {
        setError("That code didn't work. Check it, or send a new one.")
        return
      }
      await makePrimary(checked.id)
    })
  }

  if (verified && !sentTo) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Invitations go to your account&apos;s main email address, and it has none yet.
        </p>
        <Button disabled={busy} onClick={() => void attempt(() => makePrimary(verified.id))}>
          {busy ? "Saving…" : `Use ${verified.emailAddress}`}
        </Button>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  }

  return sentTo ? (
    <form onSubmit={checkCode} className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        We emailed a code to <span className="text-foreground">{sentTo.emailAddress}</span>. Enter it here.
      </p>
      <div className="grid gap-2 sm:max-w-xs">
        <Label htmlFor="email-code">Code</Label>
        <Input
          id="email-code"
          inputMode="numeric"
          autoComplete="one-time-code"
          required
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
      </div>
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Checking…" : "Confirm and send me invitations"}
        </Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={() => setSentTo(null)}>
          Use another address
        </Button>
      </div>
    </form>
  ) : (
    <form onSubmit={sendCode} className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        Invitations go to your email address, and your account doesn&apos;t have one yet. Add it here: we&apos;ll
        email you a code to confirm it.
      </p>
      <div className="grid gap-2 sm:max-w-sm">
        <Label htmlFor="add-email">Email address</Label>
        <Input
          id="add-email"
          type="email"
          autoComplete="email"
          required
          maxLength={254}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      <div>
        <Button type="submit" disabled={busy}>
          {busy ? "Sending…" : "Send me a code"}
        </Button>
      </div>
    </form>
  )
}
