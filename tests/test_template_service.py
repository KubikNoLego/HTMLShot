"""Tests for template directory discovery and validation (TemplateService.discover)."""

import json
import shutil
from pathlib import Path

import pytest

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.template import TemplateService


@pytest.fixture
def templates_root(tmp_path) -> Path:
    """Create and return an isolated temporary templates directory.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path pointing to the created templates folder.
    """
    root = tmp_path / "templates"
    root.mkdir()
    return root



class TestDiscover:
    def test_full_manifest(self, templates_root):
        folder = templates_root / "profile"
        folder.mkdir()
        (folder / "manifest.json").write_text(json.dumps({
            "name": "Профиль",
            "entrypoint": "profile.htm",
            "viewport": {"width": 320, "height": 180},
            "description": "Карточка профиля",
            "default_format": "png",
            "default_quality": 90,
        }), encoding="utf-8")
        (folder / "profile.htm").write_text("<html></html>", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        manifest = service.get("profile")
        assert isinstance(manifest, TemplateManifest)
        assert manifest.name == "Профиль"
        assert manifest.entrypoint == "profile.htm"
        assert manifest.page_size == {"width": 320, "height": 180}
        assert manifest.default_format == "png"
        assert manifest.default_quality == 90
        assert service.exists("profile")
        assert service.list_all() == [manifest]

    def test_manifest_without_optional_fields_uses_defaults(self, templates_root):
        folder = templates_root / "bare"
        folder.mkdir()
        (folder / "manifest.json").write_text(
            json.dumps({"entrypoint": "page.html"}), encoding="utf-8")
        (folder / "page.html").write_text("<html></html>", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        manifest = service.get("bare")
        assert manifest is not None
        assert manifest.name == ""
        assert manifest.page_size == {"width": 800, "height": 600}
        assert manifest.default_format is None

    def test_missing_manifest_falls_back_to_first_htm(self, templates_root):
        folder = templates_root / "fallback"
        folder.mkdir()
        (folder / "zeta.html").write_text("<html>z</html>", encoding="utf-8")
        (folder / "alpha.htm").write_text("<html>a</html>", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()
        manifest = service.get("fallback")
        assert manifest is not None
        assert manifest.name == "fallback"
        assert manifest.entrypoint in {"alpha.htm", "zeta.html"}
        assert manifest.template_file_path.exists()

    def test_missing_manifest_and_no_htm_is_skipped(self, templates_root):
        folder = templates_root / "onlycss"
        folder.mkdir()
        (folder / "style.css").write_text("body{}", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        # index.html не существует — шаблон пропускается с предупреждением
        assert service.get("onlycss") is None



    def test_broken_manifest_json_is_skipped(self, templates_root):
        broken = templates_root / "broken"
        broken.mkdir()
        (broken / "manifest.json").write_text("{not json", encoding="utf-8")
        (broken / "index.htm").write_text("<html></html>", encoding="utf-8")

        good = templates_root / "good"
        good.mkdir()
        (good / "index.htm").write_text("<html></html>", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        assert service.get("broken") is None
        assert service.get("good") is not None
        assert len(service.list_all()) == 1

    def test_invalid_manifest_fields_are_skipped(self, templates_root):
        folder = templates_root / "invalid"
        folder.mkdir()
        (folder / "manifest.json").write_text(json.dumps({
            "entrypoint": "index.htm",
            "viewport": {"width": 0, "height": -5},
        }), encoding="utf-8")
        (folder / "index.htm").write_text("<html></html>", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        assert service.get("invalid") is None

    def test_missing_entrypoint_file_is_skipped(self, templates_root):
        folder = templates_root / "ghost"
        folder.mkdir()
        (folder / "manifest.json").write_text(
            json.dumps({"entrypoint": "absent.htm"}), encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        assert service.get("ghost") is None

    def test_files_in_templates_root_ignored(self, templates_root):
        (templates_root / "readme.txt").write_text("не шаблон", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()

        assert service.list_all() == []

    def test_missing_directory_is_not_an_error(self, tmp_path):
        service = TemplateService(tmp_path / "nope")
        service.discover()
        assert service.list_all() == []

    def test_rediscover_clears_previous_state(self, templates_root):
        first = templates_root / "first"
        first.mkdir()
        (first / "index.htm").write_text("<html></html>", encoding="utf-8")

        service = TemplateService(templates_root)
        service.discover()
        assert service.exists("first")

        second = templates_root / "second"
        second.mkdir()
        (second / "index.htm").write_text("<html></html>", encoding="utf-8")
        service.discover()
        assert sorted(m.id for m in service.list_all()) == ["first", "second"]

        # удалённый шаблон исчезает после перечитывания
        shutil.rmtree(first)
        service.discover()
        assert service.get("first") is None
        assert service.exists("second")


class TestAccessors:
    def test_get_unknown_returns_none(self, templates_root):
        service = TemplateService(templates_root)
        service.discover()
        assert service.get("unknown") is None
        assert not service.exists("unknown")
        assert service.list_all() == []

