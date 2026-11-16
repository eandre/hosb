"""The frontend in a real browser: Encore's, driven with Playwright.

Signing in needs Clerk itself, which a test can't reach: the test config's
publishable key names a Clerk instance that doesn't exist. What this checks is
that the backend serves an app that boots, asks the backend for its config,
and says plainly that sign-in is unavailable rather than showing a blank page.
"""

from __future__ import annotations

from encore.testing import playwright as browsers
from encore.testing import system
from playwright.async_api import async_playwright, expect


async def test_the_app_boots_in_a_browser():
    browser_of_test = await system.browser(window=(390, 844))  # a phone
    async with async_playwright() as p:
        browser = await browsers.connect(p.chromium)
        page = await browser.new_page()

        async with page.expect_response(
            lambda r: r.url.endswith("/api/config") and r.status == 200
        ):
            await page.goto(browser_of_test.url("api") + "/events/1")

        # The deep link was answered with the app, which started, and tells
        # the member why they can't sign in rather than showing a blank page.
        await expect(page).to_have_title("House of Soft Beasts · Calendar")
        await expect(page.get_by_role("heading", name="The house isn't open yet")).to_be_visible(
            timeout=20_000
        )
        await expect(page.get_by_text("Clerk could not be loaded")).to_be_visible()
