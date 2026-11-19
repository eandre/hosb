import { Link } from "react-router"
import { cn } from "@/lib/utils"

/** The house's address, and its privacy policy and terms. */
export function SiteFooter({ className }: { className?: string }) {
  return (
    <footer className={cn("mx-auto w-full max-w-5xl px-6 py-8 text-xs text-muted-foreground", className)}>
      House of Soft Beasts · Patentgatan 2, Stockholm · <LegalLinks />
    </footer>
  )
}

export function LegalLinks() {
  return (
    <>
      <Link to="/legal/privacy" className="underline-offset-4 hover:text-foreground hover:underline">
        Privacy
      </Link>
      {" · "}
      <Link to="/legal/tos" className="underline-offset-4 hover:text-foreground hover:underline">
        Terms
      </Link>
    </>
  )
}
