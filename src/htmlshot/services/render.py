from loguru import logger
from playwright.async_api import async_playwright
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from typing import Any

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.assets import cached_css_data_uri


class ImageRender:
    """Renders HTML from Jinja2 templates with stylesheet inlining and caching."""

    _cache: dict[str, "ImageRender"] = {}

    def __init__(self, template: TemplateManifest) -> None:
        """Initialize a Jinja2 template rendering wrapper for a manifest.

        Args:
            template: The TemplateManifest defining template paths and viewport configuration.
        """
        self.env = Environment(
            loader=FileSystemLoader(str(template.template_dir.parent)))

        self.template = self.env.get_template(template.loader_name)
        self._template_dir = template.template_dir
        self._css_filename = template.css
        self.page_size = template.page_size

    @classmethod
    def for_template(cls, template: TemplateManifest) -> "ImageRender":
        """Retrieve or create a cached ImageRender instance for the given template.

        Reuses previously compiled Jinja2 template environments indexed by manifest ID
        to avoid redundant template parsing and file I/O overhead.

        Args:
            template: The template manifest to look up or initialize.

        Returns:
            The singleton ImageRender instance for this template ID.
        """
        inst = cls._cache.get(template.id)
        if inst is None:
            inst = cls(template)
            cls._cache[template.id] = inst
        return inst

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached ImageRender instances from memory."""
        cls._cache.clear()

    @staticmethod
    def _css_href(value: str) -> str:
        """Normalize a CSS reference into a valid URI for stylesheet href inclusion.

        Recognizes existing URI schemes (data:, file:, http://, https://) and leaves
        them intact. For local filesystem paths, verifies file existence and converts
        them into absolute file:// URIs.

        Args:
            value: A path or URI string pointing to a stylesheet.

        Returns:
            A normalized URI string suitable for use in an HTML link element.
        """
        if value.startswith(("data:", "file:", "http://", "https://")):
            return value
        path = Path(value)
        if path.is_file():
            return path.as_uri()
        return value

    async def render(self, context: dict[str, Any]) -> str:
        """Render the Jinja2 template with the given context and inlined styles.

        Resolves and injects the 'css_path' variable into the render context:
        either using an explicit 'css_path' provided by caller, or reading and
        caching the companion stylesheet as a data URI or file URI.

        Args:
            context: Dictionary of variables to supply to the Jinja2 template.

        Returns:
            The complete rendered HTML string ready for browser rendering.
        """
        ctx = dict(context)
        if ctx.get("css_path") is None:
            css = self._template_dir / self._css_filename
            uri = await cached_css_data_uri(css)
            if uri is not None:
                ctx["css_path"] = uri
            elif css.is_file():
                ctx["css_path"] = css.as_uri()
            else:
                ctx["css_path"] = ""
        else:
            ctx["css_path"] = self._css_href(str(ctx["css_path"]))
        return self.template.render(**ctx)




class Renderer:
    """Controls the headless Playwright Chromium instance used for raster rendering."""

    _playwright = None
    _browser = None
    _format = "webp"
    _quality = 70

    @classmethod
    async def start(cls) -> None:
        """Launch the headless Playwright browser instance with production flags.

        Starts the Playwright driver and launches Chromium with flags configured
        for reliable server-side rendering (e.g. disabled shm usage, sRGB color profile,
        hidden scrollbars, and disabled font render hinting).
        """
        cls._playwright = await async_playwright().start()
        cls._browser = await cls._playwright.chromium.launch(
            args=[
                "--disable-dev-shm-usage",
                "--force-color-profile=srgb",
                "--hide-scrollbars",
                "--font-render-hinting=none",
            ]
        )

        logger.info("Браузер Playwright запущен")

    @classmethod
    async def close(cls) -> None:
        """Shut down the headless Playwright browser and stop the runtime process.

        Closes any active Chromium browser instance and stops the underlying Playwright
        process, resetting driver references to None and handling unexpected disconnection errors.
        """
        if cls._browser is not None:
            logger.debug("Попытка закрыть браузер Playwright")
            try:
                await cls._browser.close()
            except Exception as exc:
                logger.opt(exception=exc).warning(
                    "Не удалось закрыть браузер Playwright, возможно, соединение уже разорвано")
            finally:
                cls._browser = None
                logger.debug("Браузер Playwright установлен в None")
        else:
            logger.debug("Браузер Playwright уже None, закрытие пропущено")

        if cls._playwright is not None:
            logger.debug("Попытка остановить Playwright")
            try:
                await cls._playwright.stop()
            except Exception as exc:
                logger.opt(exception=exc).warning(
                    "Не удалось остановить Playwright, возможно, соединение уже разорвано")
            finally:
                cls._playwright = None
                logger.debug("Playwright установлен в None")
        else:
            logger.debug("Playwright уже None, остановка пропущена")

        logger.info("Браузер Playwright остановлен")


    @classmethod
    async def render_html(cls, html: str, size: dict[str, int],
                          image_format: str | None = None,
                          quality: int | None = None,
                          base_path: Path | None = None) -> bytes:
        """Render an HTML string inside a headless browser page and capture a screenshot.

        Creates an isolated browser page configured with the specified viewport dimensions,
        navigates to the optional base_path URL to resolve relative resources, injects the HTML
        payload, waits for all images and DOM elements to fully finish loading, and takes
        a screenshot returning the raw image bytes.

        Args:
            html: The HTML document content to render.
            size: Viewport dimensions dictionary with 'width' and 'height' in pixels.
            image_format: Output image format ('webp', 'png', or 'jpeg'). Defaults to 'webp'.
            quality: Image quality compression setting (applicable to lossy formats). Defaults to 70.
            base_path: Optional filesystem path used to establish the document's base URL for relative assets.

        Returns:
            The captured image bytes.

        Raises:
            RuntimeError: If called before `Renderer.start()` has initialized the browser.
        """
        if cls._browser is None:
            logger.error(
                "Рендер недоступен: BrowserRender.start() не был вызван")
            raise RuntimeError(
                "BrowserRender.start() must be called first"
            )


        page = await cls._browser.new_page(
            viewport={
                "width": size["width"],
                "height": size["height"],
            }
        )

        try:
            if base_path is not None:
                await page.goto(base_path.as_uri(), wait_until="commit")
            await page.set_content(html)
            await page.wait_for_load_state("load")
            await page.locator("img").evaluate_all(
                """imgs => Promise.all(
                    imgs.map(img =>
                        img.complete
                            ? Promise.resolve()
                            : new Promise(resolve => {
                                img.onload = resolve;
                                img.onerror = resolve;
                            })
                    )
                )"""
            )
            return await page.screenshot(
                full_page=False,
                type=image_format or cls._format,
                quality=quality or cls._quality,
            )
        finally:
            await page.close()

