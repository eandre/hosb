import Link from "next/link"

export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <p className="text-muted-foreground">There's nothing here.</p>
      <Link href="/" className="mt-2 inline-block text-sm text-candle underline-offset-4 hover:underline">
        Back to the calendar
      </Link>
    </div>
  )
}
