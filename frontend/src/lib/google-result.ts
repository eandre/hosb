import { useEffect } from "react"
import { toast } from "sonner"

// How connecting went, as Google's sign-in sends the user back: ?google=.
const RESULTS: Record<string, { ok: boolean; message: string }> = {
  connected: { ok: true, message: "Google connected" },
  denied: { ok: false, message: "Google wasn't connected: access wasn't given." },
  scopes: {
    ok: false,
    message: "Google needs access to the calendars. Connect again, and leave the calendar boxes ticked.",
  },
  failed: { ok: false, message: "Connecting to Google failed. Try again." },
}

/** Says how connecting to Google went, on the page it sent the user back to
 * (`path`), and takes the ?google= off its address. */
export function useGoogleResult(path: string) {
  useEffect(() => {
    const result = RESULTS[new URLSearchParams(window.location.search).get("google") ?? ""]
    if (!result) return
    // One toast however often this runs.
    if (result.ok) toast.success(result.message, { id: "google" })
    else toast.error(result.message, { id: "google" })
    window.history.replaceState(null, "", path)
  }, [path])
}
