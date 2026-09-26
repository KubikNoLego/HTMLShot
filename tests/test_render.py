"""Tests for template caching and HTML assembly in ImageRender."""

import asyncio
import base64
from pathlib import Path

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.render import ImageRender

TEMPLATES_DIR = (Path(__file__).resolve().parents[1]
                 / "src" / "htmlshot" / "templates")


def make_manifest(template_id: str = "profile_card") -> TemplateManifest:
    """Create a test TemplateManifest pointing to a sample template directory.

    Args:
        template_id: Identifier for the template directory.

    Returns:
        A populated TemplateManifest instance.
    """
    return TemplateManifest(
        id=template_id,
        name="Профиль",
        entrypoint="profile.htm",
        css="style.css",
        dir_path=str(TEMPLATES_DIR / template_id),
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


class TestTemplateCache:
    def setup_method(self):
        ImageRender.clear_cache()

    def test_for_template_reuses_instance(self):
        manifest = make_manifest()
        first = ImageRender.for_template(manifest)
        second = ImageRender.for_template(make_manifest())
        assert first is second

    def test_different_templates_different_instances(self):
        first = ImageRender.for_template(make_manifest("profile_card"))
        second = ImageRender.for_template(TemplateManifest(
            id="open_card",
            name="Открытка",
            entrypoint="open_card.htm",
            css="style.css",
            dir_path=str(TEMPLATES_DIR / "open_card"),
        ))
        assert first is not second

    def test_clear_cache(self):
        manifest = make_manifest()
        first = ImageRender.for_template(manifest)
        ImageRender.clear_cache()
        second = ImageRender.for_template(manifest)
        assert first is not second


class TestRender:
    def setup_method(self):
        ImageRender.clear_cache()

    def test_css_inlined_as_data_uri(self):
        html = asyncio.run(
            ImageRender.for_template(make_manifest()).render(CONTEXT))
        assert 'href="data:text/css;base64,' in html

    def test_explicit_css_path_passthrough(self):
        html = asyncio.run(
            ImageRender.for_template(make_manifest()).render(
                {**CONTEXT, "css_path": "data:text/css,body{}"}))
        assert 'href="data:text/css;base64,' not in html
        assert 'href="data:text/css,body{}"' in html

    def test_explicit_css_path_file_uri(self):
        css_file = TEMPLATES_DIR / "profile_card" / "style.css"
        html = asyncio.run(
            ImageRender.for_template(make_manifest()).render(
                {**CONTEXT, "css_path": str(css_file)}))
        assert f'href="{css_file.as_uri()}"' in html

    def test_context_not_mutated(self):
        context = dict(CONTEXT)
        asyncio.run(ImageRender.for_template(make_manifest()).render(context))
        assert "css_path" not in context

    def test_css_data_uri_keeps_large_font_as_file_uri(self):
        """Ensure large font files are kept as file:// URIs rather than inlined as base64."""
        html = asyncio.run(
            ImageRender.for_template(make_manifest()).render(CONTEXT))
        start = html.index("data:text/css;base64,") + len("data:text/css;base64,")
        end = html.index('"', start)
        css = base64.b64decode(html[start:end]).decode("utf-8")
        assert "data:font/ttf;base64," not in css
        assert "url(\"file://" in css
        assert css.count(".ttf\")") == 1

    def test_html_stays_small_without_font_base64(self):
        """Ensure the rendered HTML payload size remains compact without font base64 embedding."""
        html = asyncio.run(
            ImageRender.for_template(make_manifest()).render(CONTEXT))
        assert len(html) < 32 * 1024


