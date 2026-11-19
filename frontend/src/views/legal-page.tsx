import type { ReactNode } from "react"
import { Link } from "react-router"

const CONTACT = "hello@houseofsoftbeasts.se"
const UPDATED = "19 November 2026"

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-2xl pb-8">
      <h1 className="text-3xl leading-tight sm:text-4xl">{title}</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated {UPDATED}</p>
      <div className="mt-6 space-y-4 leading-relaxed text-foreground/90 [&_h2]:mt-8 [&_h2]:text-xl [&_li]:mt-1 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5">
        {children}
      </div>
    </article>
  )
}

function Mail() {
  return (
    <a href={`mailto:${CONTACT}`} className="text-candle underline-offset-4 hover:underline">
      {CONTACT}
    </a>
  )
}

export function PrivacyPage() {
  return (
    <Page title="Privacy policy">
      <p>
        This explains what information the members&apos; calendar of the House of Soft Beasts keeps about you,
        why, and what you can do about it.
      </p>

      <h2>Who we are</h2>
      <p>
        The House of Soft Beasts is a cultural space at Patentgatan 2, Stockholm, Sweden, held by Erin Depew, who
        is responsible for your information. You can reach us at <Mail />.
      </p>

      <h2>What we keep</h2>
      <ul>
        <li>
          <strong>Your account.</strong> When you sign in: your name, email address and profile picture, whether
          you are an admin, and when you last used the calendar.
        </li>
        <li>
          <strong>Your answers to events.</strong> Whether you are going, might go or are not going, and how many
          guests you bring.
        </li>
        <li>
          <strong>Shareable links.</strong> Who made a link, and how often it was opened. To count the people who
          open one, the page keeps a random number in their browser. It does not tell us who they are.
        </li>
        <li>
          <strong>Guest sign-ups.</strong> If you sign up through a link: your full name, your email address and
          the link you used.
        </li>
        <li>
          <strong>Google Calendar, if you connect it.</strong> Your Google account&apos;s email address, the names
          of the calendars you can add events to, and access to add, change and remove the house&apos;s events in
          the calendar you choose. We keep that access encrypted. We do not read your other events.
        </li>
        <li>
          <strong>Calendar invitations, if you ask for them.</strong> We send each event to your email address as
          an invitation from the house&apos;s Google account, and read your answer (yes, maybe or no) as your
          answer to the event.
        </li>
        <li>
          <strong>Server logs.</strong> Records of requests and errors, to keep the calendar working.
        </li>
      </ul>

      <h2>Why we keep it</h2>
      <p>
        To run the calendar for the house&apos;s members: to show the events, keep track of who is coming, let the
        house prepare for each event, and do what you asked for, such as syncing your calendar. We keep it because
        it is needed for the service you signed up for, and, for the Google features, because you chose to turn
        them on. You can turn those off at any time on the settings page.
      </p>

      <h2>Who can see it</h2>
      <ul>
        <li>Other members see the names and pictures of the people going to an event, and the names of guests.</li>
        <li>The house&apos;s admins see members&apos; email addresses and the guest list for each event.</li>
        <li>
          Companies that run parts of the calendar for us handle the information only to do that: Encore (hosting),
          Clerk (sign-in) and Google (only if you use the Google Calendar features). The calendar is hosted in the
          EU. Clerk and Google may handle some of it outside the EU, with the safeguards the law requires.
        </li>
      </ul>
      <p>We do not sell your information or use it for advertising.</p>

      <h2>Google user data</h2>
      <p>
        The calendar&apos;s use of information received from Google APIs follows the{" "}
        <a
          href="https://developers.google.com/terms/api-services-user-data-policy"
          className="text-candle underline-offset-4 hover:underline"
        >
          Google API Services User Data Policy
        </a>
        , including its Limited Use requirements. We use it only to add the house&apos;s events to your calendar
        and to read your answers to the house&apos;s invitations, and we do not share it with anyone else.
      </p>

      <h2>Cookies</h2>
      <p>
        Signing in uses cookies from Clerk to keep you signed in. Pages opened from a shareable link keep a random
        number in your browser, as described above. We use no advertising or tracking cookies.
      </p>

      <h2>How long we keep it</h2>
      <p>
        We keep your information for as long as the calendar needs it to work for you. If you want it deleted, write
        to us and we will delete it.
      </p>

      <h2>Your rights</h2>
      <p>
        You can ask to see the information we have about you, to correct it, to delete it, or to get a copy of it.
        Write to <Mail />. If you think we handle your information wrongly, you can complain to the Swedish
        Authority for Privacy Protection (
        <a href="https://www.imy.se" className="text-candle underline-offset-4 hover:underline">
          IMY
        </a>
        ).
      </p>

      <h2>Changes</h2>
      <p>If we change this policy, we will update this page and the date at the top.</p>

      <p className="pt-4 text-sm text-muted-foreground">
        See also the <Link to="/legal/tos" className="underline-offset-4 hover:underline">terms of service</Link>.
      </p>
    </Page>
  )
}

export function TermsPage() {
  return (
    <Page title="Terms of service">
      <p>
        These terms are for using the members&apos; calendar of the House of Soft Beasts, a cultural space at
        Patentgatan 2, Stockholm, Sweden. By using the calendar, you agree to them.
      </p>

      <h2>Who can use it</h2>
      <p>
        The calendar is for members of the house. The house decides who is a member. Someone with a shareable link
        can see the one event it leads to and sign up for it as a guest.
      </p>

      <h2>Your account</h2>
      <p>Keep your sign-in to yourself. You are responsible for what is done with your account.</p>

      <h2>Using the calendar</h2>
      <ul>
        <li>Use it to take part in the house&apos;s events, and share your links only with people you invite.</li>
        <li>Do not try to get into parts of it that are not yours, or to disrupt it.</li>
        <li>Do not use other people&apos;s information from the calendar for anything else.</li>
      </ul>

      <h2>Events</h2>
      <p>
        Events can change or be cancelled. Places can be limited. Saying you are going, or signing up as a guest,
        helps the house plan, but the house decides who comes in. The house&apos;s own rules apply at every event.
      </p>

      <h2>Google Calendar</h2>
      <p>
        Connecting Google Calendar and getting invitations are optional. You can turn them off at any time on the
        settings page.
      </p>

      <h2>No guarantees</h2>
      <p>
        We do our best to keep the calendar working and correct, but it is provided as it is. We can change it or
        stop it. As far as the law allows, we are not responsible for losses from using it.
      </p>

      <h2>Ending</h2>
      <p>
        You can stop using the calendar at any time and ask us to delete your information. We can end your access,
        for example if you are no longer a member or do not follow these terms.
      </p>

      <h2>Law</h2>
      <p>Swedish law applies to these terms.</p>

      <h2>Changes and contact</h2>
      <p>
        If we change these terms, we will update this page and the date at the top. Questions: <Mail />.
      </p>

      <p className="pt-4 text-sm text-muted-foreground">
        See also the <Link to="/legal/privacy" className="underline-offset-4 hover:underline">privacy policy</Link>.
      </p>
    </Page>
  )
}
