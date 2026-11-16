import type { Metadata, Viewport } from "next"
import type { ReactNode } from "react"
import "./globals.css"
import { Bootstrap } from "@/components/bootstrap"

export const metadata: Metadata = {
  title: "House of Soft Beasts · Calendar",
  description: "The members' calendar of the House of Soft Beasts, a candlelit space in Stockholm.",
  icons: { icon: "/favicon.svg" },
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#15110e",
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <Bootstrap>{children}</Bootstrap>
      </body>
    </html>
  )
}
