from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_html_pages_are_available() -> None:
    assert client.get("/health").json() == {"status": "ok"}

    for path in ("/", "/students", "/students/add"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'meta name="csrf-token"' in response.text
        assert "tailwind" not in response.text.casefold()
        assert "fonts.googleapis.com" not in response.text.casefold()


def test_local_styles_scripts_and_fonts_are_served() -> None:
    asset_paths = (
        "/static/css/smartroll.css",
        "/static/js/app.js",
        "/static/js/attendance.js",
        "/static/js/students.js",
        "/static/js/add-student.js",
        "/static/fonts/IBMPlexSans-Regular.woff2",
        "/static/fonts/IBMPlexSans-SemiBold.woff2",
        "/static/fonts/IBMPlexSansCondensed-SemiBold.woff2",
        "/static/fonts/IBMPlexMono-Regular.woff2",
    )

    for path in asset_paths:
        assert client.get(path).status_code == 200


def test_openapi_contains_the_api_contract() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {
        "/health",
        "/ready",
        "/api/students",
        "/api/students/{student_id}/photos",
        "/api/students/{student_id}",
        "/api/recognition-jobs",
        "/api/jobs/{job_id}",
        "/api/jobs/{job_id}/retry",
    } <= set(paths)


def test_mutations_require_a_page_token_and_reject_foreign_origins() -> None:
    missing_token = client.post("/api/students", json={"name": "Asha Rao"})
    assert missing_token.status_code == 403
    assert missing_token.json()["detail"] == "The page token is missing or expired."

    page = client.get("/")
    token = page.text.split('meta name="csrf-token" content="', 1)[1].split('"', 1)[0]
    foreign_origin = client.post(
        "/api/students",
        json={"name": "Asha Rao"},
        headers={
            "Origin": "https://example.invalid",
            "X-CSRF-Token": token,
        },
    )
    assert foreign_origin.status_code == 403
    assert foreign_origin.json()["detail"] == "Request origin is not allowed."
