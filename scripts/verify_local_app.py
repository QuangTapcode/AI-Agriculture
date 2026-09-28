from pathlib import Path
import json

from playwright.sync_api import sync_playwright


FRONTEND_URL = "http://127.0.0.1:5174/"
BACKEND_URL = "http://127.0.0.1:8000"


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        console_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)

        health = page.request.get(f"{BACKEND_URL}/health")
        assert health.ok, f"Backend health failed: {health.status}"
        health_payload = health.json()
        assert health_payload.get("status") in {"healthy", "ok"}, health_payload

        docs = page.request.get(f"{BACKEND_URL}/docs")
        assert docs.ok, f"Swagger UI failed: {docs.status}"

        response = page.goto(FRONTEND_URL, wait_until="networkidle")
        assert response and response.ok, f"Frontend failed: {response.status if response else 'no response'}"
        assert page.title(), "Frontend has no document title"
        assert page.locator("body").inner_text().strip(), "Frontend rendered an empty body"

        page.goto(f"{FRONTEND_URL}login", wait_until="networkidle")
        assert page.locator("body").inner_text().strip(), "Login route rendered an empty body"

        screenshot = Path(".local") / "verification" / "local-app-smoke.png"
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
        assert not console_errors, f"Browser console errors: {console_errors}"
        print(json.dumps({
            "backend_health": health_payload,
            "frontend_status": response.status,
            "title": page.title(),
            "screenshot": str(screenshot),
        }, ensure_ascii=True))
        browser.close()


if __name__ == "__main__":
    main()
