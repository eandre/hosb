"use client"

import { Show, UserButton } from "@clerk/react"
import { Shield } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Candle } from "@/components/candle"
import { useMe } from "@/lib/api"
import { cn } from "@/lib/utils"

function AdminLink() {
  const { data: me } = useMe()
  const active = usePathname() === "/admin"
  if (!me?.admin) return null
  return (
    <Link
      href="/admin"
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors",
        active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Shield className="size-4" />
      <span className="sr-only sm:not-sr-only">Admin</span>
    </Link>
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
            <UserButton />
          </div>
        </Show>
      </div>
    </header>
  )
}
