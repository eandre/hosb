"use client"

import { Show, UserButton } from "@clerk/react"
import { Settings, Shield, type LucideIcon } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Candle } from "@/components/candle"
import { useMe } from "@/lib/api"
import { cn } from "@/lib/utils"

/** A page in the header: an icon, and its name where there's room. */
function NavLink({ href, icon: Icon, children }: { href: string; icon: LucideIcon; children: string }) {
  const active = usePathname() === href
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors",
        active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className="size-4" />
      <span className="sr-only sm:not-sr-only">{children}</span>
    </Link>
  )
}

function AdminLink() {
  const { data: me } = useMe()
  if (!me?.admin) return null
  return (
    <NavLink href="/admin" icon={Shield}>
      Admin
    </NavLink>
  )
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          <Candle className="h-7 shrink-0" />
          <span className="truncate font-heading text-lg leading-none tracking-tight">
            House of Soft Beasts
          </span>
        </Link>
        <Show when="signed-in">
          <div className="flex shrink-0 items-center gap-2">
            <AdminLink />
            <NavLink href="/settings" icon={Settings}>
              Settings
            </NavLink>
            <UserButton />
          </div>
        </Show>
      </div>
    </header>
  )
}
