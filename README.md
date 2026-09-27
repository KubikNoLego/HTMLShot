<div align="center">

# 📸 HTMLShot

**Render HTML templates into images — with one HTTP request.**

`template id` + JSON context → Jinja2 → headless Chromium → `webp` / `png` / `jpeg`

[![Python](https://img.shields.io/badge/Python-3.14%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Jinja2](https://img.shields.io/badge/Jinja2-B41717?style=flat-square&logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev/)

**[English](README.md)** · [Русский](README.ru.md)

</div>

---

Perfect for **profile cards, game stats, OG images, postcards, certificates** —
anywhere you need a nice picture generated from data on the fly.

## 📑 Table of contents

| | |
|---|---|
| [🧩 Features](#-features) | [🎨 Creating your own template](#-creating-your-own-template) |
| [🔄 How it works](#-how-it-works) | [🌐 API reference](#-api-reference) |
| [📁 Project structure](#-project-structure) | [⚙️ Pipeline in detail](#-pipeline-in-detail) |
| [📦 Requirements](#-requirements) | [💾 Caching](#-caching) |
| [🚀 Quickstart](#-quickstart) | [🧪 Tests](#-tests) |
| [⚙️ Configuration](#-configuration) | [🩺 FAQ](#-faq) · [👤 Author](#-author) |

---

## 🧩 Features

| | |
|---|---|
| ⚡ **FastAPI + Pydantic v2** | validation, auto-generated OpenAPI at `/docs` |
| 📂 **File-based templates** | a folder on disk is a template — auto-discovered at startup, no database |
| 🧵 **Jinja2** | `{{ var }}`, `{% for %}`, `{% if %}`, `|upper`, `|default`, `|e` |
| 🖼 **Playwright Chromium** | pixel-accurate screenshots, viewport per template, WebP / PNG / JPEG |
| 🗂 **Relative assets** | `./style.css`, fonts and images load straight from the template folder |
| 💾 **LRU image cache** | 128 entries / 256 MB, transparent via the `X-Cache` header |
| 🧪 **Fully tested** | discovery, rendering, assets, cache, settings and API |

---

## 🔄 How it works

```text
    POST /render?template=hello_card
    { "username": "kubik", "vip": true }
                    │
                    ▼
    ┌───────────────────────────────┐
    │  TemplateService.get(id)      │  manifest.json + viewport
    └───────────────┬───────────────┘
                    ▼
    ┌───────────────────────────────┐
    │  render_cache.get(sha256 key) │─── hit ───▶ return bytes · X-Cache: hit
    └───────────────┬───────────────┘
                    │ miss
                    ▼
    ┌───────────────────────────────┐
    │  ImageRender.render(context)  │  Jinja2 template → HTML
    └───────────────┬───────────────┘
                    ▼
    ┌───────────────────────────────┐
    │  Renderer.render_html(...)    │  Playwright Chromium · screenshot
    └───────────────┬───────────────┘
                    ▼
    render_cache.set(key, bytes) ──▶ Response · X-Cache: miss
```

Two caches keep things fast:

| Cache | Key | Stores |
|-------|-----|--------|
| `ImageRender._cache` | template id | compiled Jinja2 environment |
| `render_cache` | sha256(template + context + format + quality) | finished image bytes (LRU) |

**Why is it fast?** Screenshots are expensive, but a repeated identical request
returns cached bytes in milliseconds. The `X-Cache` header tells you which path
was taken.

---
## 📁 Project structure

```text
HTMLshot/
├── src/htmlshot/
│   ├── main.py                # FastAPI app + lifespan (Renderer.start/close, discover)
│   ├── config.py              # Settings (title/host/port), PROJECT_ROOT, load_settings()
│   ├── api/
│   │   ├── __init__.py        # include_routes()
│   │   ├── render.py          # POST /render, POST /render/raw
│   │   └── templates.py       # GET /templates, POST /preview
│   ├── schemas/template.py    # ViewportConfig, TemplateManifest
│   ├── services/
│   │   ├── template.py        # TemplateService: discover / get / list_all / exists
│   │   ├── render.py          # ImageRender (Jinja2) + Renderer (Playwright)
│   │   └── cache.py           # make_cache_key, RenderCache, render_cache
│   └── templates/             # ← ALL TEMPLATES LIVE HERE
│       ├── profile_card/
│       │   ├── manifest.json
│       │   ├── profile.htm
│       │   ├── style.css
│       │   └── avatar.png · bg.png · *.ttf
│       └── open_card/
│           ├── manifest.json
│           ├── open_card.htm
│           └── style.css
├── tests/                     # conftest.py + test_*.py
├── pyproject.toml             # fastapi, jinja2, playwright, loguru, ...
└── README.md · README.ru.md
```

**Suggested reading order:** `services/template.py:discover()` →
`schemas/template.py:TemplateManifest` → `services/render.py:ImageRender.render()` →
`services/render.py:Renderer.render_html()`.

---

## 📦 Requirements

- Python `>= 3.14`
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- Playwright's Chromium build

```bash
uv sync                              # install dependencies
uv run playwright install chromium   # one-time browser download
uv sync --group dev                  # + pytest for the test suite
```

Runtime dependencies: `fastapi`, `jinja2`, `playwright`, `pydantic-settings`,
`uvicorn`, `loguru`, `kubiks`.

---

## 🚀 Quickstart

```bash
git clone <repo> HTMLshot && cd HTMLshot
uv sync
uv run playwright install chromium
uv run uvicorn htmlshot.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000/docs** for the interactive Swagger UI.

```bash
# 1. what templates are available?
curl http://127.0.0.1:8000/templates

# 2. preview the HTML (instant, no screenshot)
curl -X POST "http://127.0.0.1:8000/preview?template=profile_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"kubik","avatar":"avatar.png"}'

# 3. render an image
curl -X POST "http://127.0.0.1:8000/render?template=profile_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"kubik","usertitle":"test","avatar":"avatar.png","background":"bg.png","season_title":"Season 1","common_stats":[],"season_stats":[]}' \
  --output card.webp
```

From Python:

```python
import httpx

resp = httpx.post(
    "http://127.0.0.1:8000/render",
    params={"template": "profile_card"},
    json={"username": "kubik", "avatar": "avatar.png"},
)
print(resp.headers["X-Cache"])   # miss on the first call, hit afterwards
open("card.webp", "wb").write(resp.content)
```

---
## ⚙️ Configuration

Settings live in `src/htmlshot/config.py` (`pydantic-settings`, immutable
instance cached by `load_settings()`). All variables use the `HTMLSHOT_` prefix
and are read from the environment or a `.env` file in the project root.

| Variable | Default | Meaning |
|----------|---------|---------|
| `HTMLSHOT_TITLE` | `HTMLShot` | Title shown in OpenAPI / `/docs` |
| `HTMLSHOT_HOST` | `127.0.0.1` | Bind address (use `0.0.0.0` in Docker) |
| `HTMLSHOT_PORT` | `8000` | HTTP port, must be 1–65535 |

```ini
# .env
HTMLSHOT_TITLE=HTMLShot
HTMLSHOT_HOST=0.0.0.0
HTMLSHOT_PORT=8000
```

Validation is strict: a non-numeric or out-of-range port fails at startup with a
clear Pydantic error instead of silently binding to the wrong socket.

---

## 🌐 API reference

`template`, `context`, `html`, `width` and `height` are **query parameters**;
`context` is a JSON object sent as the request body.

### `GET /templates`

Lists every discovered template.

```bash
curl http://127.0.0.1:8000/templates
```

```json
{
  "templates": [
    {
      "id": "hello_card",
      "name": "Hello card",
      "viewport": { "width": 400, "height": 200 },
      "description": "Greets a user by name"
    }
  ]
}
```

### `POST /preview?template={id}`

Renders the template and returns **HTML instead of an image** — no browser
involved, so it's the fastest way to debug a template.

```bash
curl -X POST "http://127.0.0.1:8000/preview?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"kubik","vip":true}'
```

### `POST /render?template={id}`

The main endpoint: render → screenshot → image bytes.

```bash
curl -X POST "http://127.0.0.1:8000/render?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"kubik","vip":true}' --output card.webp
```

| Response header | Meaning |
|-----------------|---------|
| `Content-Type: image/webp` | format from `default_format` (`webp` by default, or `png` / `jpeg`) |
| `X-Cache: hit` | served from the LRU cache, nothing was rendered |
| `X-Cache: miss` | freshly rendered and now cached |

### `POST /render/raw?html=...&width=...&height=...`

Renders arbitrary HTML without a template and without the cache. Always WebP.

```bash
curl -X POST "http://127.0.0.1:8000/render/raw?html=<h1>Hi</h1>&width=640&height=360" \
  --output raw.webp
```

### Status codes

| Code | When |
|------|------|
| `200` | success |
| `404` | unknown `template` id |
| `422` | missing `template` param, missing JSON body, or invalid `width`/`height` |

---
## 🎨 Creating your own template

This is the heart of HTMLShot. A template is just a **folder on disk** —
no database, no registration, no code.

```text
src/htmlshot/templates/
└── hello_card/                 <- folder name == template id
    ├── manifest.json           <- optional but recommended
    ├── index.html              <- entrypoint (Jinja2)
    ├── style.css               <- stylesheet
    └── avatar.png              <- assets live next to the template
```

`TemplateService(PROJECT_ROOT / "src" / "htmlshot" / "templates").discover()`
scans the root **once at startup** and registers every valid subfolder.

> 💡 `id` is always the folder name — you never set it in `manifest.json`,
> the service overwrites it.

---

### 1️⃣ Step 1 — create the folder

```bash
mkdir -p src/htmlshot/templates/hello_card
```

### 2️⃣ Step 2 — `manifest.json`

Tells the service which file to render, how big the picture is and in which
format to save it.

```json
{
  "name": "Hello card",
  "entrypoint": "index.html",
  "viewport": { "width": 400, "height": 200 },
  "description": "Greets a user by name",
  "default_format": "png",
  "default_quality": 90
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | *folder name* | Auto-assigned. Used in `?template=` |
| `name` | `str` | `""` | Human-readable name, shown in `GET /templates` |
| `entrypoint` | `str` | `index.html` | Jinja2 file inside the folder |
| `viewport.width` | `int` | `800` | Screenshot width in px, must be `> 0` |
| `viewport.height` | `int` | `600` | Screenshot height in px, must be `> 0` |
| `description` | `str` | `""` | Shown in `GET /templates` |
| `default_format` | `str\|null` | `null` → `webp` | `webp`, `png` or `jpeg` |
| `default_quality` | `int\|null` | `null` → `70` | Quality for lossy formats |

> ⚠️ An invalid manifest (bad JSON, `viewport: {"width": 0}`, negative height)
> makes the service **skip the template** with a warning — the rest keep working.

**No manifest?** It still works: the service picks the first `*.htm*` file in
the folder and uses `name = <folder>`, `viewport = 800x600`, no format or
quality. Great for a quick prototype, but always add a manifest for real work.

### 3️⃣ Step 3 — the HTML entrypoint

Any `*.htm*` file works: `index.html`, `index.htm`, `card.htm`, `profile.html`.
It's a **Jinja2 template** rendered with your JSON context.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="./style.css">
</head>
<body>
  <div class="card">
    <img class="avatar" src="{{ avatar }}">
    <div class="hello">Hello, {{ username | default("stranger") }}!</div>
    {% if vip %}<div class="badge">VIP</div>{% endif %}
  </div>
</body>
</html>
```

🔑 **The golden rule:** always include
`<link rel="stylesheet" href="./style.css">`. The browser loads it from the
template folder, so without it you get an unstyled screenshot.

How the context becomes variables:

```text
POST body  {"username": "kubik", "vip": true}
              ↓
Jinja       {{ username }}  →  "kubik"
            {% if vip %}     →  true  (block renders)
```

`ImageRender.render()` only interpolates your JSON context — the stylesheet is
referenced from the entrypoint with a plain relative path.

---
### 4️⃣ Step 4 — the CSS

`style.css` sits next to your entrypoint and is loaded by Chromium over
`file://` — relative `url(...)` references inside it resolve against the CSS
file itself, so keep the fonts and images in the same folder.

```css
@font-face {
  font-family: "Impact";
  src: url("Impact.ttf");          /* loaded by the browser */
}

body {
  margin: 0;
  width: 400px;                    /* match the viewport! */
  height: 200px;
  display: flex;                   /* flexbox / grid all work */
  align-items: center;
  justify-content: center;
  background: url("bg.png") no-repeat center / cover;
  font-family: "Impact", sans-serif;
  color: #fff;
}

.card   { text-align: center; }
.avatar { width: 64px; height: 64px; border-radius: 50%; }
.badge  { background: gold; color: #000; border-radius: 8px; padding: 2px 8px; }
```

**Asset rules:**

| Reference | Result |
|-----------|--------|
| `url("bg.png")` | loaded from the template folder by the browser |
| `url("Impact.ttf")` | same — no base64, so the HTML stays small |
| `url("https://...")` | fetched by the browser while the screenshot is taken |
| `url("data:...")` | used as-is |
| missing file | broken image in the result |

> 🖼 Images passed **in the JSON context are loaded by the browser too**: put the
> file next to your entrypoint and pass a relative path — Playwright resolves it
> through `base_path`.

### 5️⃣ Step 5 — restart and debug with `/preview`

`discover()` runs at startup only, so restart the server:

```bash
uv run uvicorn htmlshot.main:app --reload
curl http://127.0.0.1:8000/templates | python3 -m json.tool
```

Your template must appear in the list. Then iterate on the design with
`/preview` — it returns HTML, **no browser involved**, so it's instant:

```bash
curl -X POST "http://127.0.0.1:8000/preview?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"kubik","avatar":"avatar.png","vip":true}'
```

### 6️⃣ Step 6 — render the image

```bash
curl -X POST "http://127.0.0.1:8000/render?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"kubik","avatar":"avatar.png","vip":true}' \
  --output hello.png && file hello.png
```

Run it again → the response header says `X-Cache: hit`. 🎉

### 7️⃣ Step 7 — copy it

Duplicate the folder, rename it, done. A new folder = a new template id.

```bash
cp -r src/htmlshot/templates/hello_card src/htmlshot/templates/goodbye_card
# then edit manifest.json -> "name": "Goodbye card"
```

---
### 🧠 Advanced Jinja2

Loops, conditions and filters work as in any Jinja2 template:

```html
<h2>{{ season_title | upper }}</h2>

{% for s in common_stats %}
  <div class="stat">
    <span class="icon">{{ s.icon }}</span>
    <b>{{ s.value }}</b>
    <i>{{ s.label }}</i>
  </div>
{% else %}
  <p class="muted">No stats yet</p>
{% endfor %}

{% if vip %}<div class="badge">VIP</div>{% endif %}
{{ comment | e }}   {# escape untrusted input! #}
```

The environment uses Jinja2 defaults, so **escape untrusted input with `|e`**.

### 🚧 Discovery rules & pitfalls

`TemplateService.discover()` behaviour:

| Situation | Result |
|-----------|--------|
| File (not a folder) in the templates root | ignored |
| Valid `manifest.json` + existing entrypoint | ✅ registered |
| Broken `manifest.json` / `viewport <= 0` | ⚠️ skipped, logged as error |
| Entrypoint file doesn't exist | ⚠️ skipped, logged as warning |
| No `manifest.json` | falls back to the first `*.htm*`, then `index.html` |
| `discover()` called again | the registry is cleared first |

Common mistakes:

| Symptom | Cause |
|---------|-------|
| Template missing from `/templates` | wrong folder name, or the manifest was rejected |
| Unstyled output | forgot `<link rel="stylesheet" href="./style.css">` |
| Screenshot is cut off | CSS `body` size ≠ `viewport` size |
| Broken image | the `url()` path is relative to the **CSS file**, not the entrypoint |
| 404 after adding a folder | the server wasn't restarted — no hot-reload for templates |

---

## ⚙️ Pipeline in detail

**1 · Resolve the template** — `api/render.py` looks up
`request.app.state.templates.get(template_id)` and raises `404` if unknown.

**2 · Check the cache** — `make_cache_key(template_id, context, format, quality)`
builds a SHA-256 of a canonical JSON dump; a hit returns immediately.

**3 · Render HTML** — `ImageRender.for_template(manifest)` returns a cached
singleton per id (the compiled Jinja2 environment is reused). `.render(context)`
copies your dict (it never mutates it), then calls `template.render(**ctx)`.

**4 · Screenshot** — `Renderer.render_html()`:

```text
new_page(viewport={width, height})
  → page.goto(base_path.as_uri())      # so relative assets resolve
  → page.set_content(html)
  → page.wait_for_load_state("load")
  → wait for every <img> to complete
  → page.screenshot(full_page=False, type=format, quality=quality)
```

**5 · Cache & respond** — the bytes go into the LRU, and the response is
returned with `X-Cache: miss`.

Chromium is launched once in the lifespan with production flags:

```text
--disable-dev-shm-usage   --force-color-profile=srgb
--hide-scrollbars         --font-render-hinting=none
```

---

## 💾 Caching

**1 · Image LRU** — `services/cache.py`

```python
make_cache_key(template_id, context, image_format, quality) -> str  # sha256 hex
```

- Canonical JSON with `sort_keys=True` → dict order doesn't matter.
- `ensure_ascii=False, default=str` → non-serializable values never crash.
- `RenderCache(max_entries=128, max_bytes=256 MB)` — a real LRU on an
  `OrderedDict`: a `get()` moves the entry to the end, and `set()` evicts the
  oldest entries until both limits are satisfied.

**2 · Jinja environments** — `ImageRender.for_template()` keeps one compiled
template per id in a class-level dict, so parsing happens once.

> ♻️ The cache is per-process. Run several workers → each one has its own
> browser and its own cache.

---
## 🧪 Tests

```bash
uv sync --group dev
uv run pytest -v
uv run pytest tests/test_template_service.py -v   # single file
```

| Fixture | What it does |
|---------|--------------|
| `make_template()` | builds a temp template folder (`index.htm` + `style.css` + manifest `320x180`) and re-runs `discover()` |
| `client` | `TestClient` with a no-op lifespan (no browser launched) |
| `renderer_stub` | monkeypatches `Renderer.render_html`, records calls, returns `b"fake-image-bytes"` |
| `clear_global_caches` | autouse — clears `render_cache` and `ImageRender._cache` around each test |

Covered: manifest validation, discovery fallbacks, context interpolation,
cache keys, LRU eviction, settings parsing, and every endpoint.

---

## 🩺 FAQ

<details>
<summary>404 <code>Template X not found</code></summary>

The folder name is the template id. Check `GET /templates` — if it's missing,
`discover()` skipped it (broken `manifest.json`, `viewport <= 0`, or a missing
entrypoint file). Look at the loguru warnings on startup.
</details>

<details>
<summary>The image has no styling</summary>

You forgot `<link rel="stylesheet" href="./style.css">`, or `style.css` isn't in
the template folder. Check with `POST /preview` — the returned HTML shows the
actual `href`.
</details>

<details>
<summary><code>BrowserRender.start() must be called first</code></summary>

`Renderer.start()` runs in the FastAPI lifespan. You either bypassed the
lifespan or Playwright failed to launch. Check the logs.
</details>

<details>
<summary>Playwright: browser executable doesn't exist</summary>

```bash
uv run playwright install chromium
uv run playwright install-deps chromium   # Linux system libraries
```
</details>

<details>
<summary>Images or fonts don't show up</summary>

Use relative paths: inside CSS `url()` they resolve against the CSS file, in the
JSON context against the entrypoint (`base_path`). The files must live inside the
template folder — every asset is loaded by the browser itself.
</details>

<details>
<summary>First render is slow</summary>

Chromium cold start plus Jinja compile. Subsequent identical requests are served
from the LRU cache in milliseconds — check the `X-Cache` header.
</details>

<details>
<summary>I added a template but the server doesn't see it</summary>

`discover()` only runs at startup. Restart the server.
</details>
