/** The calendar's views, each at its own path, so that a reload keeps it. */
export const views = { upcoming: "/", week: "/week", calendar: "/calendar", past: "/past" } as const
export type View = keyof typeof views
export const viewPaths = Object.values(views)
