"""Tests for template caching and HTML assembly in ImageRender."""

import asyncio
import base64
from pathlib import Path

import pytest

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.assets import CSS_INLINE_LIMIT
from htmlshot.services.render import ImageRender

# Локальный шрифт должен быть крупнее CSS_INLINE_LIMIT: тогда inline_css_urls()
# подставит абсолютный file:// URI вместо base64 и HTML не раздуется.
FONT_SIZE = CSS_INLINE_LIMIT + 1024

TEMPLATE_HTML = (
    "<!doctype html>\n"
    "<html>\n"
    '<head><link rel="stylesheet" href="{{ css_path }}"></head>\n'
    "<body><span class=\"username\">{{ username }}</span></body>\n"
    "</html>\n"
)

TEMPLATE_CSS = (
    "@font-face {\n"
    "    font-family: \"Impact\";\n"
    "    src: url(\"./impact.ttf\");\n"
    "}\n"
    "\n"
    "body { margin: 0; }\n"
)


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
    """Create a template directory on disk with an oversized local font.

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
        (tdir / "impact.ttf").write_bytes(b"\0" * FONT_SIZE)
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
        css="style.css",
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

    def test_css_inlined_as_data_uri(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        html = asyncio.run(ImageRender.for_template(manifest).render(CONTEXT))
        assert 'href="data:text/css;base64,' in html

    def test_explicit_css_path_passthrough(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        html = asyncio.run(ImageRender.for_template(manifest).render(
            {**CONTEXT, "css_path": "data:text/css,body{}"}))
        assert 'href="data:text/css;base64,' not in html
        assert 'href="data:text/css,body{}"' in html

    def test_explicit_css_path_file_uri(self, make_template):
        tdir = make_template("profile_card", "profile.htm")
        manifest = make_manifest(tdir, "profile_card")
        css_file = tdir / "style.css"
        html = asyncio.run(ImageRender.for_template(manifest).render(
            {**CONTEXT, "css_path": str(css_file)}))
        assert f'href="{css_file.as_uri()}"' in html

    def test_context_not_mutated(self, make_template):
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        context = dict(CONTEXT)
        asyncio.run(ImageRender.for_template(manifest).render(context))
        assert "css_path" not in context

    def test_css_data_uri_keeps_large_font_as_file_uri(self, make_template):
        """Ensure large font files are kept as file:// URIs rather than inlined as base64."""
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        html = asyncio.run(ImageRender.for_template(manifest).render(CONTEXT))
        start = html.index("data:text/css;base64,") + len("data:text/css;base64,")
        end = html.index('"', start)
        css = base64.b64decode(html[start:end]).decode("utf-8")
        assert "data:font/ttf;base64," not in css
        assert "url(\"file://" in css
        assert css.count(".ttf\")") == 1

    def test_html_stays_small_without_font_base64(self, make_template):
        """Ensure the rendered HTML payload size remains compact without font base64 embedding."""
        manifest = make_manifest(
            make_template("profile_card", "profile.htm"), "profile_card")
        html = asyncio.run(ImageRender.for_template(manifest).render(CONTEXT))
        assert len(html) < 32 * 1024


