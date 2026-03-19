"""Tests for InterviewSystem — project management."""

import pytest

from src.interview.models import ProjectCreateRequest
from src.interview.system import InterviewSystem, reset_projects


@pytest.fixture(autouse=True)
def _reset():
    reset_projects()
    yield
    reset_projects()


@pytest.fixture()
def system() -> InterviewSystem:
    return InterviewSystem()


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_creates_project(self, system):
        req = ProjectCreateRequest(name="测试项目", industry="finance")
        resp = await system.create_project("tenant-1", req)
        assert resp.name == "测试项目"
        assert resp.tenant_id == "tenant-1"
        assert resp.status == "active"

    @pytest.mark.asyncio
    async def test_project_has_id(self, system):
        req = ProjectCreateRequest(name="P1", industry="ecommerce")
        resp = await system.create_project("t1", req)
        assert resp.id  # non-empty

    @pytest.mark.asyncio
    async def test_business_domain_optional(self, system):
        req = ProjectCreateRequest(name="P1", industry="finance", business_domain="银行")
        resp = await system.create_project("t1", req)
        assert resp.business_domain == "银行"


class TestListProjects:
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, system):
        await system.create_project("t1", ProjectCreateRequest(name="A", industry="finance"))
        await system.create_project("t2", ProjectCreateRequest(name="B", industry="finance"))
        t1_projects = await system.list_projects("t1")
        assert len(t1_projects) == 1
        assert t1_projects[0].name == "A"

    @pytest.mark.asyncio
    async def test_empty_list(self, system):
        projects = await system.list_projects("nobody")
        assert projects == []
