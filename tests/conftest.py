"""Shared test fixtures: global cache clearing, temporary templates, and API client."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from htmlshot.services import assets
from htmlshot.services.cache import render_cache
from htmlshot.services.render import ImageRender, Renderer
from htmlshot.services.template import TemplateService

DEFAULT_MANIFEST = {
    "name": "Тестовый шаблон",
    "entrypoint": "index.htm",
    "css": "style.css",
    "viewport": {"width": 320, "height": 180},
    "description": "Временный шаблон для тестов",
}

DEFAULT_HTML = (
    "<!doctype html>\n"
    "<html>\n"
    '<head><link rel="stylesheet" href="{{ css_path }}"></head>\n'
    '<body><span class="username">{{ username }}</span></body>\n'
    "</html>\n"
)

DEFAULT_CSS = "body { margin: 0; }\n"


@pytest.fixture(autouse=True)
def clear_global_caches():
    """Ensure global caches (image LRU cache, template instances, CSS URIs) do not leak between test runs.

    Clears the rendered image byte cache, compiled Jinja2 template instances,
    and cached CSS data URIs both prior to test execution and immediately following teardown.
    """

    def _clear():
        render_cache.clear()
        ImageRender.clear_cache()
        assets._CSS_CACHE.clear()

    _clear()
    yield
    _clear()


@pytest.fixture
def templates_root(tmp_path) -> Path:
    """Create and return an isolated temporary directory for storing test template folders.

    Args:
        tmp_path: Pytest-provided temporary path fixture.

    Returns:
        Path pointing to an empty 'templates' directory inside the temp directory.
    """
    root = tmp_path / "templates"
    root.mkdir()
    return root


@pytest.fixture
def template_service(templates_root) -> TemplateService:
    """Provide a TemplateService instance targeting the temporary templates directory without initial discovery.

    Args:
        templates_root: The temporary templates root directory fixture.

    Returns:
        An undiscovered TemplateService instance.
    """
    return TemplateService(templates_root)


@pytest.fixture
def make_template(template_service):
    """Provide a helper callable to create a template directory on disk and trigger service discovery.

    Allows tests to create mock templates with customizable manifest dictionaries,
    HTML entrypoint contents, and CSS stylesheets, then automatically runs `discover()`
    on the test template service.

    Args:
        template_service: The temporary TemplateService fixture.

    Returns:
        A factory function `_make(template_id, *, manifest, html, css)` returning the template directory Path.
    """

    def _make(template_id="demo", *, manifest=DEFAULT_MANIFEST,
              html=DEFAULT_HTML, css=DEFAULT_CSS):
        tdir = template_service.templates_dir / template_id
        tdir.mkdir(parents=True, exist_ok=True)
        if manifest is not None:
            (tdir / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
        (tdir / "index.htm").write_text(html, encoding="utf-8")
        (tdir / "style.css").write_text(css, encoding="utf-8")
        template_service.discover()
        return tdir

    return _make


@asynccontextmanager
async def _noop_lifespan(app):
    """Provide a dummy no-op FastAPI lifespan context manager that skips launching Playwright.

    Used by test fixtures to bypass headless browser initialization during API endpoint tests.

    Args:
        app: The FastAPI application instance.

    Yields:
        None.
    """
    yield


@pytest.fixture
def client(template_service, monkeypatch):
    """Provide a FastAPI TestClient configured with a mock lifespan and temporary template service.

    Overrides the default application lifespan to prevent browser startup, binds the isolated
    test template service to `app.state.templates`, and provides a TestClient context.

    Args:
        template_service: The temporary TemplateService fixture.
        monkeypatch: Pytest monkeypatch fixture for patching application lifespan.

    Yields:
        A configured TestClient instance.
    """
    from htmlshot.main import app

    monkeypatch.setattr(app.router, "lifespan_context", _noop_lifespan)
    app.state.templates = template_service
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def renderer_stub(monkeypatch):
    """Mock `Renderer.render_html` to prevent browser execution and capture rendering invocations.

    Intercepts calls to `Renderer.render_html`, recording arguments (HTML markup, size,
    image format, quality, and base path) into an inspection list and returning mock bytes.

    Args:
        monkeypatch: Pytest monkeypatch fixture for overriding the class method.

    Returns:
        A SimpleNamespace containing a `calls` list with all recorded render call parameter dicts.
    """
    calls: list[dict] = []

    async def fake_render_html(html, size, image_format=None,
                               quality=None, base_path=None):
        calls.append({
            "html": html,
            "size": dict(size),
            "image_format": image_format,
            "quality": quality,
            "base_path": base_path,
        })
        return b"fake-image-bytes"

    monkeypatch.setattr(Renderer, "render_html", fake_render_html)
    return SimpleNamespace(calls=calls)


