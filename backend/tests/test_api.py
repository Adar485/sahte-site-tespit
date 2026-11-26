"""Submission, persistence, result and history through the API (SQLite)."""

from sqlalchemy import select

from app.models import Analysis, AnalysisModule
from app.services import engine


def stored(session_factory, analysis_id):
    with session_factory() as session:
        analysis = session.get(Analysis, analysis_id)
        rows = session.execute(select(AnalysisModule).where(AnalysisModule.analysis_id == analysis_id)).scalars()
        return analysis, {row.module: row for row in rows}


def test_url_only_submission_is_persisted_without_risk(client, session_factory):
    response = client.post("/api/analyze", json={"url": "  Example.com.login.example.net/Yol?x=1  "})
    assert response.status_code == 202
    body = response.json()
    assert (body["state"], body["status"], body["error"]) == ("done", "partial", None)

    analysis, rows = stored(session_factory, body["id"])
    assert analysis.submitted_url == "Example.com.login.example.net/Yol?x=1"
    assert analysis.final_url is analysis.risk_level is analysis.risk_score is analysis.model_version is None
    assert (analysis.status, analysis.analysis_mode, analysis.error_code) == ("partial", "url_only", None)

    assert set(rows) == {"url", "visual", "text", "html"}
    url = rows["url"]
    assert url.status == "completed" and url.summary and url.findings and url.duration_ms is not None
    assert url.features["featureSchemaVersion"] == "1.0"
    assert url.features["address"]["normalizedUrl"] == "https://example.com.login.example.net/Yol?x=1"
    for name in ("visual", "text", "html"):
        assert rows[name].status == "skipped" and rows[name].features is None and rows[name].findings == []

    result = client.get(f"/api/result/{body['id']}").json()["result"]
    assert result["status"] == "partial" and result["analysisMode"] == "url_only"
    assert result["risk"] is result["failure"] is result["modelVersion"] is None
    assert result["modules"]["url"]["data"] == url.features
    assert result["modules"]["visual"]["status"] == "skipped"


def test_history_lists_url_only_records_without_risk_or_failure(client):
    analysis_id = client.post("/api/analyze", json={"url": "https://example.com/"}).json()["id"]
    page = client.get("/api/history").json()
    assert page["items"][0]["id"] == analysis_id
    assert (page["items"][0]["status"], page["items"][0]["riskLevel"]) == ("partial", None)
    assert page["counts"] == {"all": 1, "low": 0, "suspicious": 0, "high": 0, "failed": 0}
    for result_filter in ("low", "suspicious", "high", "failed"):
        assert client.get("/api/history", params={"result": result_filter}).json()["items"] == []

    assert client.delete(f"/api/analyses/{analysis_id}").status_code == 204
    assert client.get(f"/api/result/{analysis_id}").status_code == 404


def test_invalid_input_creates_no_record(client):
    for url, code in (("ftp://example.com", "unsupported_scheme"), ("https://example.com:99999", "invalid_port"), ("", "empty")):
        response = client.post("/api/analyze", json={"url": url})
        assert response.status_code == 422 and response.json()["detail"]["code"] == code
    assert client.get("/api/history").json()["total"] == 0


def test_credentials_are_rejected_before_anything_is_stored_or_logged(client, session_factory, caplog):
    secret = "s3cret-pw"
    bodies = [
        {"url": f"https://someone:{secret}@example.com/"},
        {"url": f"someone:{secret}@example.com"},
        # Malformed request bodies must not echo the input either.
        {"uri": f"https://someone:{secret}@example.com/"},
        {"url": [f"https://someone:{secret}@example.com/"]},
    ]
    for body in bodies:
        response = client.post("/api/analyze", json=body)
        assert response.status_code == 422
        assert secret not in response.text and "someone" not in response.text
    broken_json = client.post(
        "/api/analyze", content=f'{{"url": "https://someone:{secret}@', headers={"Content-Type": "application/json"}
    )
    assert broken_json.status_code == 422 and secret not in broken_json.text

    first = client.post("/api/analyze", json=bodies[0]).json()["detail"]
    assert first["code"] == "credentials_not_allowed" and "kabul edilmiyor" in first["message"]
    assert secret not in caplog.text
    with session_factory() as session:
        assert session.query(Analysis).count() == 0 and session.query(AnalysisModule).count() == 0


def test_inspection_error_is_stored_consistently_and_sanitized(client, session_factory, monkeypatch):
    def broken(url):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(engine, "run_url_inspection", broken)
    body = client.post("/api/analyze", json={"url": "https://example.com/"}).json()
    assert body["status"] == "failed" and "secret" not in body["error"]["message"]

    analysis, rows = stored(session_factory, body["id"])
    assert (analysis.status, analysis.error_code, analysis.risk_level) == ("failed", "unknown", None)
    assert rows["url"].status == "failed" and rows["url"].features is None
    assert rows["url"].error_message == engine.URL_FAILURE_MESSAGE
    assert rows["visual"].status == "skipped"

    result = client.get(f"/api/result/{body['id']}").json()["result"]
    assert result["failure"]["stage"] == "url_check" and result["risk"] is None


def test_older_records_are_still_served(client, session_factory):
    with session_factory() as session:
        failed = Analysis(
            submitted_url="https://old.example.com/",
            status="failed",
            error_code="service_unavailable",
            error_message="Analiz motoru kullanılamıyor.",
        )
        full = Analysis(
            submitted_url="https://full.example.com/", status="completed", risk_level="low", risk_score=10, analysis_mode="full"
        )
        session.add_all([failed, full])
        session.commit()

    old = client.get(f"/api/result/{failed.id}").json()["result"]
    assert old["status"] == "failed" and old["modules"]["url"]["status"] == "skipped"
    assert old["failure"]["stage"] == "url_check"
    assert client.get(f"/api/result/{full.id}").json()["result"]["risk"] == {
        "level": "low",
        "score": 10,
        "summary": None,
        "recommendation": None,
    }
