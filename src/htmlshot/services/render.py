from loguru import logger
from playwright.async_api import async_playwright
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from typing import Any

from htmlshot.schemas.template import TemplateManifest


class ImageRender:
    """Renders HTML from Jinja2 templates with context interpolation and caching."""

    _cache: dict[str, "ImageRender"] = {}

    def __init__(self, template: TemplateManifest) -> None:
        """Initialize a Jinja2 template rendering wrapper for a manifest.

        Args:
            template: The TemplateManifest defining template paths and viewport configuration.
        """
        self.env = Environment(
            loader=FileSystemLoader(str(template.template_dir.parent)))

        self.template = self.env.get_template(template.loader_name)
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

    async def render(self, context: dict[str, Any]) -> str:
        """Render the Jinja2 template with the given context variables.

        Copies the caller's context dictionary (it is never mutated) and renders
        the Jinja2 template. Stylesheets and other assets are referenced from the
        entrypoint with relative paths (e.g. `./style.css`) and resolved by the
        browser through `base_path` during screenshot rendering.

        Args:
            context: Dictionary of variables to supply to the Jinja2 template.

        Returns:
            The complete rendered HTML string ready for browser rendering.
        """
        ctx = dict(context)
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

