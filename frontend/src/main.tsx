import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { App } from "./App"
import { SetupNeeded } from "./pages/setup-needed"
import { request } from "./lib/api"
import { ErrorBoundary } from "./components/error-boundary"

const root = createRoot(document.getElementById("root")!)

// The Clerk publishable key comes from the backend's config, so one build
// serves every environment.
request<{ clerkPublishableKey: string }>("/api/config")
  .then(({ clerkPublishableKey }) => {
    root.render(
      <StrictMode>
        {clerkPublishableKey ? (
          <ErrorBoundary
            fallback={(err) => (
              <SetupNeeded
                error={
                  err.message.includes("Clerk")
                    ? "Clerk could not be loaded, so you can't sign in right now. Check your connection and try again."
                    : `Something went wrong: ${err.message}`
                }
              />
            )}
          >
            <App publishableKey={clerkPublishableKey} />
          </ErrorBoundary>
        ) : (
          <SetupNeeded />
        )}
      </StrictMode>,
    )
  })
  .catch((err: Error) => {
    root.render(<SetupNeeded error={err.message} />)
  })
