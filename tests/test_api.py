import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import init_db

# Initialize database tables for testing
init_db()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_demo_clean_match_scenario(client):
    response = client.post("/api/demo/clean_match")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "MATCHED"
    assert data["match_score"] == 100.0
    assert data["has_exceptions"] is False


def test_demo_price_mismatch_scenario(client):
    response = client.post("/api/demo/price_mismatch")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "VARIANCE_DETECTED"
    assert data["has_exceptions"] is True
    assert data["variance_total"] > 0
    assert "dispute_email_draft" in data


def test_dashboard_stats(client):
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_processed" in data
    assert "match_rate_pct" in data
    assert "total_variance_amount" in data


def test_human_review_workflow(client):
    # 1. Create a demo scenario with variance
    demo_res = client.post("/api/demo/quantity_shortage")
    rec = demo_res.json()
    rec_id = rec["id"]

    # 2. Submit a human review decision: ESCALATE
    review_res = client.post(
        f"/api/reconciliations/{rec_id}/review",
        json={
            "action": "ESCALATED",
            "notes": "Escalated to vendor account manager regarding 10 unit shortfall",
            "reviewer_name": "Senior Auditor Jane Doe"
        }
    )
    assert review_res.status_code == 200
    updated = review_res.json()["record"]
    assert updated["status"] == "ESCALATED"
    assert updated["reviewer_action"] == "ESCALATED"
    assert "shortfall" in updated["reviewer_notes"]

