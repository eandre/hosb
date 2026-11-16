import { useSyncExternalStore } from "react"

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener("change", onChange)
      return () => list.removeEventListener("change", onChange)
    },
    () => window.matchMedia(query).matches,
  )
}

/** Wide enough for dialogs rather than bottom drawers. */
export const useIsDesktop = () => useMediaQuery("(min-width: 768px)")
