from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.request import urlopen

import pytest
from PIL import Image
from playwright.sync_api import Browser, Page, Route, sync_playwright


FASTAPI_ROOT = Path(__file__).resolve().parents[1]
AXE_PATH = Path(__file__).resolve().parent / "vendor" / "axe.min.js"
SCREENSHOT_ROOT = FASTAPI_ROOT / "var" / "screenshots"
SYNTHETIC_STUDENTS = [
    {
        "id": 1,
        "name": "Asha Rao",
        "created_at": "2026-09-08T08:00:00Z",
        "enrollment_state": "ready",
    },
    {
        "id": 2,
        "name": "Noah Martin",
        "created_at": "2026-09-08T08:10:00Z",
        "enrollment_state": "pending",
    },
]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    port = _free_port()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(FASTAPI_ROOT)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=FASTAPI_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                pytest.fail(f"Uvicorn stopped before testing:\n{output}")
            try:
                with urlopen(f"{url}/health", timeout=0.2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("Uvicorn did not become ready for browser testing.")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    with sync_playwright() as playwright:
        options = {"headless": True}
        if chrome.is_file():
            options["executable_path"] = str(chrome)
        instance = playwright.chromium.launch(**options)
        yield instance
        instance.close()


@pytest.fixture()
def synthetic_photo(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic-classroom.png"
    Image.new("RGB", (800, 520), color=(219, 231, 234)).save(path)
    return path


def _json(route: Route, payload: object, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload),
    )


def _roster_api(route: Route) -> None:
    if route.request.method == "DELETE":
        route.fulfill(status=204, body="")
        return
    _json(
        route,
        {
            "items": SYNTHETIC_STUDENTS,
            "page": 1,
            "page_size": 100,
            "total": len(SYNTHETIC_STUDENTS),
        },
    )


def _axe_violations(page: Page) -> list[dict[str, object]]:
    page.add_script_tag(path=str(AXE_PATH))
    result = page.evaluate(
        """async () => await axe.run(document, {
          runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']}
        })"""
    )
    return result["violations"]


def _assert_no_axe_violations(page: Page) -> None:
    violations = _axe_violations(page)
    details = [
        f"{item['id']}: {item['help']} "
        f"({', '.join(str(node['target']) for node in item['nodes'])})"
        for item in violations
    ]
    assert not violations, "\n".join(details)


@pytest.mark.parametrize("width", [1440, 1024, 768, 375, 320])
def test_responsive_pages_have_no_horizontal_overflow_and_pass_axe(
    browser: Browser, live_server: str, width: int
) -> None:
    page = browser.new_page(viewport={"width": width, "height": 1000})
    page.route("**/api/students*", _roster_api)
    SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)

    for path, name in (("/", "attendance"), ("/students", "roster"), ("/students/add", "enroll")):
        page.goto(f"{live_server}{path}")
        page.wait_for_load_state("networkidle")
        has_overflow = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        assert not has_overflow, f"{name} overflows at {width}px"
        _assert_no_axe_violations(page)
        page.screenshot(
            path=SCREENSHOT_ROOT / f"{name}-{width}.png",
            full_page=True,
        )

    page.close()


def test_attendance_polling_announces_review_results(
    browser: Browser, live_server: str, synthetic_photo: Path
) -> None:
    page = browser.new_page(viewport={"width": 1024, "height": 900})
    poll_count = 0

    def recognition_api(route: Route) -> None:
        nonlocal poll_count
        if route.request.method == "POST":
            _json(route, {"job_id": "11111111-1111-1111-1111-111111111111", "state": "pending"}, 202)
            return
        poll_count += 1
        if poll_count == 1:
            _json(
                route,
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "kind": "recognition",
                    "state": "running",
                    "student_id": None,
                    "attempt_count": 1,
                    "result": None,
                    "error_code": None,
                    "error_message": None,
                    "created_at": "2026-09-08T08:00:00Z",
                    "started_at": "2026-09-08T08:00:01Z",
                    "finished_at": None,
                },
            )
            return
        _json(
            route,
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "kind": "recognition",
                "state": "succeeded",
                "student_id": None,
                "attempt_count": 1,
                "result": {
                    "recognized_students": [{"id": 1, "name": "Asha Rao"}],
                    "needs_review": [
                        {"reason": "unknown_face", "box": {}, "candidates": []}
                    ],
                    "not_recognized_students": [{"id": 2, "name": "Noah Martin"}],
                    "unknown_face_count": 1,
                },
                "error_code": None,
                "error_message": None,
                "created_at": "2026-09-08T08:00:00Z",
                "started_at": "2026-09-08T08:00:01Z",
                "finished_at": "2026-09-08T08:00:02Z",
            },
        )

    page.route("**/api/recognition-jobs", recognition_api)
    page.route("**/api/jobs/**", recognition_api)
    page.goto(live_server)
    page.wait_for_load_state("networkidle")
    page.set_input_files("#classroom-photo", synthetic_photo)
    page.get_by_role("button", name="Start recognition").click()
    page.get_by_text("Recognition finished. Review the suggestions.").wait_for(timeout=6000)

    assert page.locator("#recognized-list").get_by_text("Asha Rao").is_visible()
    assert page.locator("#review-list").get_by_text("No roster match").is_visible()
    assert page.locator("#not-recognized-list").get_by_text("Noah Martin").is_visible()
    page.screenshot(
        path=SCREENSHOT_ROOT / "attendance-review-1024.png",
        full_page=True,
    )
    _assert_no_axe_violations(page)
    page.close()


def test_network_failure_has_recovery_copy(
    browser: Browser, live_server: str, synthetic_photo: Path
) -> None:
    page = browser.new_page(viewport={"width": 768, "height": 900})
    page.route("**/api/recognition-jobs", lambda route: route.abort("failed"))
    page.goto(live_server)
    page.set_input_files("#classroom-photo", synthetic_photo)
    page.get_by_role("button", name="Start recognition").click()

    page.locator("#photo-message").get_by_text(
        "SmartRoll could not connect. Check the connection and try again."
    ).wait_for()
    assert page.get_by_role("button", name="Start recognition").is_enabled()
    _assert_no_axe_violations(page)
    page.close()


def test_expired_result_is_explicit(
    browser: Browser, live_server: str, synthetic_photo: Path
) -> None:
    page = browser.new_page(viewport={"width": 768, "height": 900})

    def expired_api(route: Route) -> None:
        if route.request.method == "POST":
            _json(route, {"job_id": "22222222-2222-2222-2222-222222222222", "state": "pending"}, 202)
            return
        _json(
            route,
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "kind": "recognition",
                "state": "succeeded",
                "student_id": None,
                "attempt_count": 1,
                "result": {"expired": True},
                "error_code": None,
                "error_message": None,
                "created_at": "2026-09-08T08:00:00Z",
                "started_at": "2026-09-08T08:00:01Z",
                "finished_at": "2026-09-08T08:00:02Z",
            },
        )

    page.route("**/api/recognition-jobs", expired_api)
    page.route("**/api/jobs/**", expired_api)
    page.goto(live_server)
    page.set_input_files("#classroom-photo", synthetic_photo)
    page.get_by_role("button", name="Start recognition").click()

    page.get_by_text("This scan has expired").wait_for(timeout=4000)
    _assert_no_axe_violations(page)
    page.close()


def test_mobile_navigation_and_delete_dialog_focus(
    browser: Browser, live_server: str
) -> None:
    page = browser.new_page(viewport={"width": 375, "height": 850})
    page.route("**/api/students*", _roster_api)
    page.goto(f"{live_server}/students")
    page.wait_for_load_state("networkidle")

    menu = page.get_by_role("button", name="Menu")
    menu.click()
    assert menu.get_attribute("aria-expanded") == "true"
    page.keyboard.press("Escape")
    assert menu.get_attribute("aria-expanded") == "false"
    assert page.evaluate("document.activeElement === document.querySelector('.nav-toggle')")

    delete_button = page.get_by_role("button", name="Delete Asha Rao")
    delete_button.click()
    assert page.evaluate("document.activeElement.id") == "cancel-delete"
    _assert_no_axe_violations(page)
    page.keyboard.press("Shift+Tab")
    assert page.evaluate("document.activeElement.id") == "confirm-delete"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "cancel-delete"
    page.keyboard.press("Escape")
    assert not page.locator("#delete-dialog").evaluate("dialog => dialog.open")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Delete Asha Rao"
    page.close()


def test_enrollment_file_validation_recovers(
    browser: Browser, live_server: str, synthetic_photo: Path
) -> None:
    page = browser.new_page(viewport={"width": 768, "height": 900})
    page.goto(f"{live_server}/students/add")
    page.locator("#student-name").fill("Synthetic Student")
    page.set_input_files(
        "#student-photos",
        {"name": "not-an-image.txt", "mimeType": "text/plain", "buffer": b"invalid"},
    )
    page.get_by_role("button", name="Enroll student").click()
    page.get_by_text("not-an-image.txt is not a JPEG or PNG image.").wait_for()
    _assert_no_axe_violations(page)

    page.set_input_files("#student-photos", synthetic_photo)
    assert page.locator("#photos-error").is_hidden()
    assert page.locator("#selected-photos").get_by_text(synthetic_photo.name, exact=True).is_visible()
    _assert_no_axe_violations(page)
    page.close()


def test_mobile_supporting_actions_follow_results_and_remove_the_photo(
    browser: Browser, live_server: str, synthetic_photo: Path
) -> None:
    page = browser.new_page(viewport={"width": 375, "height": 900})
    page.goto(live_server)
    page.set_input_files("#classroom-photo", synthetic_photo)

    mobile_actions = page.locator("#proof-actions-mobile")
    assert mobile_actions.is_visible()
    assert page.locator("#proof-actions").is_hidden()
    assert mobile_actions.bounding_box()["y"] > page.locator("#scan-panel").bounding_box()["y"]
    _assert_no_axe_violations(page)

    mobile_actions.get_by_role("button", name="Remove").click()
    assert page.get_by_role("heading", name="Take attendance").is_visible()
    assert page.locator("#scan-panel").is_hidden()
    assert mobile_actions.is_hidden()
    page.close()


def test_pending_job_exposes_safe_redispatch(
    browser: Browser, live_server: str, synthetic_photo: Path
) -> None:
    page = browser.new_page(viewport={"width": 768, "height": 900})

    def pending_api(route: Route) -> None:
        if route.request.method == "POST":
            _json(
                route,
                {
                    "job_id": "33333333-3333-3333-3333-333333333333",
                    "state": "pending",
                },
                202,
            )
            return
        _json(
            route,
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "kind": "recognition",
                "state": "pending",
                "student_id": None,
                "attempt_count": 0,
                "result": None,
                "error_code": None,
                "error_message": None,
                "created_at": "2026-09-08T08:00:00Z",
                "started_at": None,
                "finished_at": None,
            },
        )

    page.route("**/api/recognition-jobs", pending_api)
    page.route("**/api/jobs/**", pending_api)
    page.goto(live_server)
    page.set_input_files("#classroom-photo", synthetic_photo)
    page.get_by_role("button", name="Start recognition").click()

    page.get_by_role("button", name="Retry this scan").wait_for(timeout=6000)
    page.close()


def test_recognition_frame_has_no_decorative_motion(
    browser: Browser, live_server: str
) -> None:
    context = browser.new_context(
        viewport={"width": 1024, "height": 900}, reduced_motion="reduce"
    )
    page = context.new_page()
    page.goto(live_server)
    page.locator("#proof-frame").evaluate(
        "frame => { frame.dataset.state = 'processing'; }"
    )

    animation_name = page.locator("#proof-frame").evaluate(
        "line => getComputedStyle(line).animationName"
    )
    assert animation_name == "none"
    context.close()


def test_controls_keep_minimum_target_size_and_text_zoom_remains_usable(
    browser: Browser, live_server: str
) -> None:
    page = browser.new_page(viewport={"width": 768, "height": 1000})
    page.goto(live_server)
    undersized = page.locator(
        "button:not([hidden]), a.button:not([hidden]), label.button:not([hidden])"
    ).evaluate_all(
        """controls => controls
          .filter(control => {
            const rect = control.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44);
          })
          .map(control => ({text: control.textContent.trim(), rect: control.getBoundingClientRect().toJSON()}))"""
    )
    assert undersized == []

    page.evaluate("document.documentElement.style.fontSize = '200%'")
    assert page.get_by_role("heading", name="Take attendance").is_visible()
    assert page.locator("label[for=classroom-photo]").is_visible()
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    page.close()
