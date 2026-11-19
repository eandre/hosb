import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Route, Routes } from "react-router"
import "./index.css"
import { Bootstrap } from "@/components/bootstrap"
import { AdminPage } from "@/views/admin-page"
import { EventPage } from "@/views/event-page"
import { EventsPage } from "@/views/events-page"
import { PrivacyPage, TermsPage } from "@/views/legal-page"
import { NotFound } from "@/views/not-found"
import { SettingsPage } from "@/views/settings-page"
import { SharePage } from "@/views/share-page"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Bootstrap>
        <Routes>
          <Route path="/" element={<EventsPage />} />
          <Route path="/events/:slug" element={<EventPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/s/:link" element={<SharePage />} />
          <Route path="/legal/privacy" element={<PrivacyPage />} />
          <Route path="/legal/tos" element={<TermsPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Bootstrap>
    </BrowserRouter>
  </StrictMode>,
)
