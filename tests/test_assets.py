"""Tests for embedding assets into data URIs and stylesheet URL resolution (services/assets)."""

import asyncio
import base64

import pytest

from htmlshot.services import assets
from htmlshot.services.assets import (
    MAX_INLINE_LENGTH,
    cached_css_data_uri,
    css_data_uri,
    data_uri,
    fetch_asset,
    guess_mime,
    inline_context_assets,
    inline_css_urls,
    looks_like_asset,
    read_local,
)


class TestGuessMime:
    @pytest.mark.parametrize("name, mime", [
        ("a.png", "image/png"),
        ("photo.JPG", "image/jpeg"),
        ("pic.jpeg", "image/jpeg"),
        ("font.ttf", "font/ttf"),
        ("anim.webp", "image/webp"),
        ("file without extension", "application/octet-stream"),
        ("archive.zip", "application/octet-stream"),
    ])
    def test_known_extensions(self, name, mime):
        assert guess_mime(name) == mime


class TestDataUri:
    def test_encodes_bytes(self):
        assert data_uri(b"hi", "text/plain") == "data:text/plain;base64,aGk="

    def test_round_trip(self):
        payload = "Юникод ✨".encode("utf-8")
        uri = data_uri(payload, "image/png")
        encoded = uri.split(",", 1)[1]
        assert base64.b64decode(encoded) == payload


class TestLooksLikeAsset:
    def test_empty_and_data_uri_rejected(self, tmp_path):
        assert not looks_like_asset("", tmp_path)
        assert not looks_like_asset("data:image/png;base64,AAAA", tmp_path)

    def test_multiline_rejected(self, tmp_path):
        assert not looks_like_asset("line1\nline2", tmp_path)

    def test_too_long_rejected(self, tmp_path):
        assert not looks_like_asset("a" * (MAX_INLINE_LENGTH + 1), tmp_path)

    def test_remote_urls_accepted(self, tmp_path):
        assert looks_like_asset("http://example.com/a.png", tmp_path)
        assert looks_like_asset("https://example.com/a.png", tmp_path)
        assert looks_like_asset("file:///tmp/a.png", tmp_path)

    def test_local_existing_file_accepted(self, tmp_path):
        (tmp_path / "img.png").write_bytes(b"x")
        assert looks_like_asset("img.png", tmp_path)

    def test_local_missing_file_rejected(self, tmp_path):
        assert not looks_like_asset("missing.png", tmp_path)

    def test_no_base_dir_rejected_for_relative(self):
        assert not looks_like_asset("img.png", None)

    def test_unknown_scheme_rejected(self, tmp_path):
        assert not looks_like_asset("ftp://host/a.png", tmp_path)


class TestReadLocal:
    def test_relative_path(self, tmp_path):
        (tmp_path / "a.txt").write_text("data", encoding="utf-8")
        assert read_local("a.txt", tmp_path) == b"data"

    def test_file_uri(self, tmp_path):
        target = tmp_path / "a.txt"
        target.write_text("data", encoding="utf-8")
        assert read_local(target.as_uri(), tmp_path) == b"data"

    def test_missing_file_returns_none(self, tmp_path):
        assert read_local("nope.txt", tmp_path) is None

    def test_no_base_dir_returns_none(self, tmp_path):
        assert read_local("a.txt", None) is None




class TestFetchAsset:
    def test_local_file_becomes_data_uri(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"PNGDATA")
        uri = asyncio.run(fetch_asset("a.png", tmp_path))
        expected = "data:image/png;base64," + base64.b64encode(b"PNGDATA").decode()
        assert uri == expected

    def test_data_uri_returns_none(self, tmp_path):
        assert asyncio.run(fetch_asset("data:image/png;base64,AAAA", tmp_path)) is None

    def test_missing_local_file_returns_none(self, tmp_path):
        assert asyncio.run(fetch_asset("missing.png", tmp_path)) is None

    def test_file_uri_local(self, tmp_path):
        target = tmp_path / "pic.png"
        target.write_bytes(b"HELLO")
        uri = asyncio.run(fetch_asset(target.as_uri(), None))
        assert uri == "data:image/png;base64," + base64.b64encode(b"HELLO").decode()
    def test_remote_http_asset(self, monkeypatch):
        class FakeResponse:
            content = b"REMOTE_DATA"
            def raise_for_status(self): pass

        class FakeClient:
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get(self, url): return FakeResponse()

        import httpx2
        monkeypatch.setattr(httpx2, "AsyncClient", FakeClient)
        uri = asyncio.run(fetch_asset("http://example.com/pic.png"))
        assert uri == "data:image/png;base64," + base64.b64encode(b"REMOTE_DATA").decode()

    def test_too_large_asset_returns_none(self, tmp_path):
        from htmlshot.services.assets import MAX_INLINE_BYTES
        (tmp_path / "huge.png").write_bytes(b"X" * (MAX_INLINE_BYTES + 1))
        assert asyncio.run(fetch_asset("huge.png", tmp_path)) is None



class TestInlineCssUrls:
    def test_inlines_relative_local_file(self, tmp_path):
        (tmp_path / "icon.png").write_bytes(b"ICON")
        css = 'button { background: url("icon.png"); }'
        result = asyncio.run(inline_css_urls(css, tmp_path))
        assert 'url("data:image/png;base64,' in result

    def test_missing_file_keeps_original_reference(self, tmp_path):
        css = 'body { background: url("missing.png"); }'
        result = asyncio.run(inline_css_urls(css, tmp_path))
        assert result == css

    def test_data_uri_kept_asis(self, tmp_path):
        css = 'body { background: url("data:image/png;base64,AAAA"); }'
        result = asyncio.run(inline_css_urls(css, tmp_path))
        assert result == css

    def test_multiple_references(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"A")
        (tmp_path / "b.gif").write_bytes(b"B")
        css = 'i { background: url("a.png"); cursor: url(b.gif); }'
        result = asyncio.run(inline_css_urls(css, tmp_path))
        assert result.count("data:") == 2


class TestCssDataUri:
    def test_missing_file_returns_none(self, tmp_path):
        assert asyncio.run(css_data_uri(tmp_path / "no.css")) is None

    def test_encodes_css_text(self, tmp_path):
        css = tmp_path / "s.css"
        css.write_text("body { color: red; }", encoding="utf-8")
        uri = asyncio.run(css_data_uri(css))
        assert uri is not None
        decoded = base64.b64decode(uri.split(",", 1)[1]).decode("utf-8")
        assert decoded == "body { color: red; }"


class TestCachedCssDataUri:
    def test_returns_none_for_missing_file(self, tmp_path):
        assert asyncio.run(cached_css_data_uri(tmp_path / "no.css")) is None

    def test_caches_until_file_changes(self, tmp_path):
        import os

        css = tmp_path / "s.css"
        css.write_text("body { color: red; }", encoding="utf-8")

        first = asyncio.run(cached_css_data_uri(css))
        second = asyncio.run(cached_css_data_uri(css))
        assert first == second
        assert len(assets._CSS_CACHE) == 1

        # изменяем файл и mtime — ключ кэша должен измениться
        css.write_text("body { color: blue; }", encoding="utf-8")
        stat = css.stat()
        os.utime(css, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

        third = asyncio.run(cached_css_data_uri(css))
        assert third != first
        assert len(assets._CSS_CACHE) == 2


class TestInlineContextAssets:
    def test_replaces_local_files_recursively(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"A")
        context = {
            "avatar": "a.png",
            "nested": {"bg": "a.png", "title": "обычный текст"},
            "list": ["a.png", 42],
            "tuple": ("a.png",),
            "number": 7,
        }
        result = asyncio.run(inline_context_assets(context, tmp_path))

        assert result["avatar"].startswith("data:image/png;base64,")
        assert result["nested"]["bg"].startswith("data:image/png;base64,")
        assert result["nested"]["title"] == "обычный текст"
        assert result["list"][0].startswith("data:image/png;base64,")
        assert result["list"][1] == 42
        assert isinstance(result["tuple"], tuple)
        assert result["tuple"][0].startswith("data:image/png;base64,")
        assert result["number"] == 7

    def test_missing_file_keeps_value(self, tmp_path):
        result = asyncio.run(inline_context_assets({"avatar": "no.png"}, tmp_path))
        assert result["avatar"] == "no.png"

    def test_context_not_mutated(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"A")
        context = {"avatar": "a.png"}
        asyncio.run(inline_context_assets(context, tmp_path))
        assert context == {"avatar": "a.png"}
