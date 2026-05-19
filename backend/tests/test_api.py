"""Integration-style tests against the FastAPI app (no real cloud calls)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from main import app


def _mock_settings() -> Settings:
    return Settings(use_mock_data=True)


app.dependency_overrides[get_settings] = _mock_settings

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "providers" in data


def test_root_returns_metadata():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "CloudLens API"


def test_recommendations_returns_list():
    resp = client.get("/api/v1/recommendations/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_recommendations"] > 0
    assert data["total_projected_savings"] > 0
    assert len(data["recommendations"]) == data["total_recommendations"]


def test_recommendations_filter_by_provider():
    resp = client.get("/api/v1/recommendations/?provider=aws")
    assert resp.status_code == 200
    data = resp.json()
    for rec in data["recommendations"]:
        assert rec["provider"] == "aws"


def test_recommendations_filter_by_type():
    resp = client.get("/api/v1/recommendations/?rec_type=idle_instance")
    assert resp.status_code == 200
    data = resp.json()
    for rec in data["recommendations"]:
        assert rec["recommendation_type"] == "idle_instance"


def test_recommendations_filter_by_min_savings():
    min_s = 200.0
    resp = client.get(f"/api/v1/recommendations/?min_savings={min_s}")
    assert resp.status_code == 200
    for rec in resp.json()["recommendations"]:
        assert rec["projected_monthly_savings"] >= min_s


def test_cost_summary_structure():
    resp = client.get("/api/v1/costs/summary")
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "total_monthly_spend",
        "total_projected_savings",
        "savings_percentage",
        "by_provider",
        "by_service",
        "by_region",
        "by_account",
        "trend",
    }
    assert required_keys.issubset(data.keys())
    assert data["total_monthly_spend"] > 0
    assert isinstance(data["trend"], list)
    assert len(data["trend"]) > 0


def test_cost_summary_trend_has_date_and_amount():
    resp = client.get("/api/v1/costs/summary")
    trend = resp.json()["trend"]
    for point in trend[:5]:
        assert "date" in point
        assert "amount" in point
        assert isinstance(point["amount"], float)


def test_recommendation_not_found():
    resp = client.get("/api/v1/recommendations/nonexistent-id-xyz")
    assert resp.status_code == 404


def test_export_pdf_returns_pdf_bytes():
    resp = client.post(
        "/api/v1/export/pdf",
        json={
            "include_providers": ["aws", "azure", "gcp"],
            "include_types": ["idle_instance", "unattached_volume", "oversized_rds"],
            "min_savings": 0,
            "format": "pdf",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # PDF magic bytes
    assert resp.content[:4] == b"%PDF"


def test_export_pdf_with_min_savings_filter():
    resp = client.post(
        "/api/v1/export/pdf",
        json={"min_savings": 500.0, "format": "pdf"},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
