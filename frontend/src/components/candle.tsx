import { cn } from "@/lib/utils"

/** The house's mark: a lit candle. */
export function Candle({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 40" aria-hidden className={cn("h-8 w-auto", className)}>
      <path
        d="M12 2c3 3.8 4.3 6.6 4.3 9a4.3 4.3 0 0 1-8.6 0c0-2.4 1.3-5.2 4.3-9Z"
        className="fill-candle drop-shadow-[0_0_6px_rgba(232,165,75,0.7)]"
      />
      <path d="M12 9.5c1 1.4 1.5 2.4 1.5 3.3a1.5 1.5 0 0 1-3 0c0-.9.5-1.9 1.5-3.3Z" className="fill-[#fff3d6]" />
      <rect x="7" y="18" width="10" height="20" rx="2" className="fill-foreground" />
    </svg>
  )
}
