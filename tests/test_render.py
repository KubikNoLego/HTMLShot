"""Tests for template caching and HTML assembly in ImageRender."""

import asyncio
from pathlib import Path

import pytest

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.render import ImageRender

TEMPLATE_HTML = """
<!doctype html>
<html>
<head><link rel="stylesheet" href="./style.css"></head>
<body><span class="username">{{ username }}</span></body>
</html>
"""

TEMPLATE_CSS = "body { margin: 0; }"

CONTEXT = {
    "username": "kubik",
    "usertitle": "тест",
    "avatar": "avatar.png",
    "background": "bg.png",
    "season_title": "Сезон 1",
    "common_stats": [{"icon": "⚔", "value": "10", "label": "Килы"}],
    "season_stats": [{"icon": "★", "value": "5", "label": "Победы"}],
}


@pytest.fixture
def make_template(tmp_path):
    """Create a template directory on disk with an entrypoint and a stylesheet.

    Tests must not depend on the real `src/htmlshot/templates` content: those
    folders are git-ignored local custom templates and are absent on CI.

    Args:
        tmp_path: Pytest-provided temporary path fixture.

    Returns:
        A factory creating a template directory and returning its path.
    """
    root = tmp_path / "templates"

    def _make(template_id: str, entrypoint: str) -> Path:
        tdir = root / template_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / entrypoint).write_text(TEMPLATE_HTML, encoding="utf-8")
        (tdir / "style.css").write_text(TEMPLATE_CSS, encoding="utf-8")
        return tdir

    return _make


def make_manifest(tdir: Path, template_id: str,
                  entrypoint: str = "profile.htm") -> TemplateManifest:
    """Create a test TemplateManifest pointing to a generated template directory.

    Args:
        tdir: Path to the template directory created by the `make_template` fixture.
        template_id: Identifier for the template directory.
        entrypoint: Template entrypoint filename inside `tdir`.

    Returns:
        A populated TemplateManifest instance.
    """
    return TemplateManifest(
        id=template_id,
        name="Профиль",
        entrypoint=entrypoint,
        dir_path=str(tdir),
    )


class TestTemplateCache:
    def setup_method(self):
        ImageRender.clear_cache()

    def test_for_template_reuses_instance(self, make_template):
        tdir = make_template("profile_card", "profile.htm")
        first = ImageRender.for_template(make_manifest(tdir, "profile_card"))
        second = ImageRender.for_template(make_manifest(tdir, "profile_card"))
        assert first is second

    def test_different_templates_different_instances(self, make_template):
        first = ImageRender.for_template(make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card"))
        second = ImageRender.for_template(make_manifest(
            make_template("open_card", "open_card.htm"),
            "open_card", "open_card.htm"))
        assert first is not second

    def test_clear_cache(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        first = ImageRender.for_template(manifest)
        ImageRender.clear_cache()
        second = ImageRender.for_template(manifest)
        assert first is not second


class TestRender:
    def setup_method(self):
        ImageRender.clear_cache()

    def test_renders_context_into_html(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        html = asyncio.run(ImageRender.for_template(manifest).render(CONTEXT))
        assert '<span class="username">kubik</span>' in html

    def test_stylesheet_linked_relative_to_entrypoint(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        html = asyncio.run(ImageRender.for_template(manifest).render(CONTEXT))
        assert 'href="./style.css"' in html

    def test_context_not_mutated(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        context = dict(CONTEXT)
        asyncio.run(ImageRender.for_template(manifest).render(context))
        assert context == CONTEXT
