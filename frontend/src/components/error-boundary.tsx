import { Component, type ReactNode } from "react"

/** Shows fallback instead of a blank page when rendering fails, as it does
 * when Clerk can't be loaded. */
export class ErrorBoundary extends Component<
  { fallback: (error: Error) => ReactNode; children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    return this.state.error ? this.props.fallback(this.state.error) : this.props.children
  }
}
