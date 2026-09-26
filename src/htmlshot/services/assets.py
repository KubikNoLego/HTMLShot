"""Helpers that embed external assets into rendered HTML as data URIs."""

import base64
import re
from pathlib import Path
from typing import Any

import httpx2
from loguru import logger

ASSET_TIMEOUT = 10.0
MAX_INLINE_BYTES = 8 * 1024 * 1024
MAX_INLINE_LENGTH = 2048

_SQ = chr(39)
_DQ = chr(34)
_QUOTES = _DQ + _SQ

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

URL_REF_RE = re.compile(
    r"url\(\s*([" + _QUOTES + r"]?)([^" + _QUOTES + r")]+)\1\s*\)")

# Локальные ресурсы крупнее этого порога не встраиваем в CSS base64,
# а подставляем абсолютным file:// URI: HTML рендера не раздувается
# (шрифт Impact ~136 КБ даёт ~184 КБ base64 на каждый запрос).
CSS_INLINE_LIMIT = 64 * 1024

_CSS_CACHE: dict[tuple[str, int, int], str] = {}


def guess_mime(name: str) -> str:
    """Determine the standard MIME content type for a given filename or path.

    Inspects the file extension of the provided name against a known mapping
    of common image and web font formats. Defaults to 'application/octet-stream'
    when the extension is unmapped or absent.

    Args:
        name: A file name, relative path, or URL from which to extract the extension.

    Returns:
        The matching MIME type string (e.g. 'image/png', 'font/woff2') or a fallback.
    """
    return MIME_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


def data_uri(data: bytes, mime: str) -> str:
    """Encode raw binary data into an RFC 2397 compliant base64 data URI string.

    Args:
        data: The binary payload to encode.
        mime: The MIME type specifying the media type of the payload.

    Returns:
        A data URI formatted as 'data:<mime>;base64,<payload>'.
    """
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")


def looks_like_asset(value: str, base_dir: Path | None) -> bool:
    """Check whether a string represents a reference to a local or remote asset.

    Evaluates whether the string conforms to supported asset URL schemes (http://,
    https://, file://) or points to an existing file relative to the specified base directory.
    Strings that are empty, contain newline characters, exceed the maximum inline length,
    or already represent data URIs are rejected.

    Args:
        value: The string candidate to evaluate.
        base_dir: Optional base directory used to resolve relative local file paths.

    Returns:
        True if the string appears to be a valid asset reference; False otherwise.
    """
    if not value or len(value) > MAX_INLINE_LENGTH or "\n" in value:
        return False
    if value.startswith("data:"):
        return False
    if value.startswith(("http://", "https://", "file://")):
        return True
    if base_dir is None or "://" in value:
        return False
    return (base_dir / value).is_file()


def read_local(reference: str, base_dir: Path | None) -> bytes | None:
    """Read the binary content of a locally referenced filesystem asset.

    Resolves the provided asset reference, supporting file:// URI schemes,
    relative paths resolved against base_dir, and absolute paths. Catches
    and logs filesystem read errors gracefully.

    Args:
        reference: A file path or file:// URI pointing to the asset.
        base_dir: Base directory used to resolve relative paths.

    Returns:
        The file contents as bytes if readable and existing, or None otherwise.
    """
    if reference.startswith("file://"):
        path = Path(reference[7:])
    elif base_dir is not None:
        path = base_dir / reference
    else:
        return None
    try:
        if path.is_file():
            return path.read_bytes()
    except OSError as exc:
        logger.warning("Не удалось прочитать ресурс {}: {}", path, exc)
    return None





async def fetch_asset(reference: str, base_dir: Path | None = None) -> str | None:
    """Retrieve an asset by reference and convert its contents to a base64 data URI.

    Handles both remote HTTP/HTTPS resources and local filesystem references. Enforces
    maximum download and inline byte limits. If the asset cannot be retrieved, is too large,
    or is already a data URI, returns None.

    Args:
        reference: The URL or filesystem path to the asset.
        base_dir: Optional base directory to resolve relative paths against.

    Returns:
        A base64-encoded data URI string, or None if fetching failed or exceeded size limits.
    """
    if reference.startswith("data:"):
        return None

    if reference.startswith(("http://", "https://")):
        try:
            async with httpx2.AsyncClient(timeout=ASSET_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(reference)
                response.raise_for_status()
                data = response.content
        except Exception as exc:
            logger.warning("Не удалось загрузить ресурс {}: {}", reference, exc)
            return None
    else:
        data = read_local(reference, base_dir)

    if data is None or len(data) > MAX_INLINE_BYTES:
        return None

    return data_uri(data, guess_mime(reference.split("?")[0]))


async def inline_css_urls(css_text: str, css_dir: Path) -> str:
    """Scan and replace url(...) references inside CSS text with data URIs or file URIs.

    Searches for all url(...) occurrences within the stylesheet. Small referenced assets
    are inlined as base64 data URIs. Local assets larger than `CSS_INLINE_LIMIT` (such as
    heavy font files) are resolved to absolute file:// URIs instead of being base64-encoded,
    preventing unnecessary bloating of the generated HTML payload during rendering.

    Args:
        css_text: The raw CSS stylesheet content to process.
        css_dir: The directory where the CSS stylesheet resides, used for path resolution.

    Returns:
        The transformed CSS string with url() references inlined or updated.
    """
    parts: list[str] = []
    position = 0
    for match in URL_REF_RE.finditer(css_text):
        parts.append(css_text[position:match.start()])
        reference = match.group(2).strip()
        uri = None
        if not reference.startswith(("data:", "http://", "https://")):
            path = (Path(reference[7:])
                    if reference.startswith("file://") else css_dir / reference)
            try:
                if path.is_file() and path.stat().st_size > CSS_INLINE_LIMIT:
                    uri = path.resolve().as_uri()
            except OSError as exc:
                logger.warning("Не удалось оценить размер ресурса {}: {}",
                               reference, exc)
        if uri is None:
            uri = await fetch_asset(reference, css_dir)
        parts.append("url(" + _DQ + uri + _DQ + ")" if uri else match.group(0))
        position = match.end()
    parts.append(css_text[position:])
    return "".join(parts)




async def css_data_uri(css_path: Path) -> str | None:
    """Read a CSS file from disk, inline its URL references, and return a data URI.

    Reads the UTF-8 text from the provided CSS path, resolves nested url() references
    using `inline_css_urls`, and packages the resulting stylesheet into a 'text/css'
    data URI.

    Args:
        css_path: Filesystem path to the CSS file.

    Returns:
        A base64 data URI representing the inlined CSS, or None if the file cannot be read.
    """
    try:
        text = css_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Не удалось прочитать CSS {}: {}", css_path, exc)
        return None
    text = await inline_css_urls(text, css_path.parent)
    return data_uri(text.encode("utf-8"), "text/css")


async def cached_css_data_uri(css_path: Path) -> str | None:
    """Return an inlined CSS data URI, utilizing an in-memory cache based on file mtime.

    Tracks file path, modification time, and file size to avoid re-reading and re-inlining
    unchanged CSS files across multiple render calls.

    Args:
        css_path: Filesystem path to the CSS file.

    Returns:
        The cached or freshly generated CSS data URI string, or None if the file is missing.
    """
    try:
        stat = css_path.stat()
    except OSError:
        return None
    key = (str(css_path), stat.st_mtime_ns, stat.st_size)
    cached = _CSS_CACHE.get(key)
    if cached is not None:
        return cached
    uri = await css_data_uri(css_path)
    if uri is not None:
        _CSS_CACHE[key] = uri
    return uri


async def inline_context_assets(context: dict[str, Any], base_dir: Path | None) -> dict[str, Any]:
    """Recursively traverse a template context dictionary and replace asset paths with data URIs.

    Clones the input dictionary structure (including nested dicts, lists, and tuples)
    and converts string values that match local or remote assets into base64 data URIs.
    Non-asset strings and other data types remain unmodified.

    Args:
        context: The input template rendering context dictionary.
        base_dir: Base directory for resolving relative asset paths.

    Returns:
        A new context dictionary with asset references replaced by data URIs.
    """

    async def walk(value: Any) -> Any:
        if isinstance(value, str):
            if looks_like_asset(value, base_dir):
                uri = await fetch_asset(value, base_dir)
                return uri if uri else value
            return value
        if isinstance(value, dict):
            return {key: await walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [await walk(item) for item in value]
        if isinstance(value, tuple):
            return tuple([await walk(item) for item in value])
        return value

    return {key: await walk(item) for key, item in context.items()}

