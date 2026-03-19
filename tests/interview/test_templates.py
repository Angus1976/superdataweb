"""Tests for industry template CRUD and seed data."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interview.models import IndustryTemplateRequest
from src.interview.router import install_exception_handlers, router
from src.interview import templates as tmpl_store


@pytest.fixture(autouse=True)
def _reset():
    tmpl_store.reset_templates()
    yield
    tmpl_store.reset_templates()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    return TestClient(app)


class TestSeedData:
    def test_three_builtin_templates(self):
        templates = tmpl_store.list_templates()
        assert len(templates) == 3

    def test_seed_covers_all_industries(self):
        templates = tmpl_store.list_templates()
        industries = {t.industry for t in templates}
        assert industries == {"finance", "ecommerce", "manufacturing"}

    def test_all_builtin(self):
        for t in tmpl_store.list_templates():
            assert t.is_builtin is True


class TestTemplateCRUD:
    def test_create_template(self):
        req = IndustryTemplateRequest(name="自定义", industry="finance", system_prompt="prompt")
        created = tmpl_store.create_template(req)
        assert created.name == "自定义"
        assert created.is_builtin is False

    def test_get_template_by_id(self):
        req = IndustryTemplateRequest(name="T1", industry="ecommerce", system_prompt="p")
        created = tmpl_store.create_template(req)
        fetched = tmpl_store.get_template(created.id)
        assert fetched is not None
        assert fetched.name == "T1"

    def test_get_template_not_found(self):
        assert tmpl_store.get_template("nonexistent") is None

    def test_update_template(self):
        req = IndustryTemplateRequest(name="Old", industry="finance", system_prompt="p")
        created = tmpl_store.create_template(req)
        updated = tmpl_store.update_template(
            created.id,
            IndustryTemplateRequest(name="New", industry="finance", system_prompt="p2"),
        )
        assert updated is not None
        assert updated.name == "New"

    def test_update_nonexistent_returns_none(self):
        req = IndustryTemplateRequest(name="X", industry="finance", system_prompt="p")
        assert tmpl_store.update_template("bad-id", req) is None

    def test_filter_by_industry(self):
        templates = tmpl_store.list_templates(industry="finance")
        assert all(t.industry == "finance" for t in templates)

    def test_get_template_by_industry(self):
        t = tmpl_store.get_template_by_industry("ecommerce")
        assert t is not None
        assert t.industry == "ecommerce"


class TestTemplateAPI:
    def test_list_templates_endpoint(self, client: TestClient):
        resp = client.get("/api/interview/templates")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_create_template_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/interview/templates",
            json={"name": "API模板", "industry": "finance", "system_prompt": "p"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "API模板"

    def test_update_template_endpoint(self, client: TestClient):
        create_resp = client.post(
            "/api/interview/templates",
            json={"name": "Old", "industry": "finance", "system_prompt": "p"},
        )
        tid = create_resp.json()["id"]
        update_resp = client.put(
            f"/api/interview/templates/{tid}",
            json={"name": "New", "industry": "finance", "system_prompt": "p2"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "New"

    def test_update_nonexistent_returns_404(self, client: TestClient):
        resp = client.put(
            "/api/interview/templates/bad-id",
            json={"name": "X", "industry": "finance", "system_prompt": "p"},
        )
        assert resp.status_code == 404
