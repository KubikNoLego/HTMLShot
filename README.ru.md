<div align="center">

# 📸 HTMLShot

**Превращаем HTML-шаблоны в картинки — одним запросом.**

`id шаблона` + JSON → Jinja2 → headless Chromium → `webp` / `png` / `jpeg`

[![Python](https://img.shields.io/badge/Python-3.14%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Jinja2](https://img.shields.io/badge/Jinja2-B41717?style=flat-square&logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev/)

[English](README.md) · **[Русский](README.ru.md)**

</div>

---

Идеально для **карточек профилей, игровой статистики, OG-картинок, открыток,
сертификатов** — везде, где из данных нужно быстро сделать красивую картинку.

## 📑 Содержание

| | |
|---|---|
| [🧩 Возможности](#-возможности) | [🎨 Создание своего шаблона](#-создание-своего-шаблона) |
| [🔄 Как это работает](#-как-это-работает) | [🌐 API](#-api) |
| [📁 Структура](#-структура) | [⚙️ Конвейер подробно](#-конвейер-подробно) |
| [📦 Требования](#-требования) | [💾 Кэширование](#-кэширование) |
| [🚀 Быстрый старт](#-быстрый-старт) | [🧪 Тесты](#-тесты) |
| [⚙️ Настройка](#-настройка) | [🩺 FAQ](#-faq) · [👤 Автор](#-автор) |

---
## 🧩 Возможности

| | |
|---|---|
| ⚡ **FastAPI + Pydantic v2** | валидация и автогенерируемая документация на `/docs` |
| 📂 **Файловые шаблоны** | папка на диске = шаблон, автопоиск при старте, без БД |
| 🧵 **Jinja2** | `{{ var }}`, `{% for %}`, `{% if %}`, `|upper`, `|default`, `|e` |
| 🖼 **Playwright Chromium** | точные скриншоты, свой viewport на шаблон, WebP / PNG / JPEG |
| 🗂 **Относительные ассеты** | `./style.css`, шрифты и картинки грузятся прямо из папки шаблона |
| 💾 **LRU-кэш картинок** | 128 записей / 256 МБ, виден в заголовке `X-Cache` |
| 🧪 **Покрыт тестами** | поиск шаблонов, рендеринг, ассеты, кэш, настройки, API |

---

## 🔄 Как это работает

```text
    POST /render?template=hello_card
    { "username": "кубик", "vip": true }
                    │
                    ▼
    ┌───────────────────────────────┐
    │  TemplateService.get(id)      │  manifest.json + viewport
    └───────────────┬───────────────┘
                    ▼
    ┌───────────────────────────────┐
    │  render_cache.get(sha256 key) │─── hit ───▶ отдаём байты · X-Cache: hit
    └───────────────┬───────────────┘
                    │ miss
                    ▼
    ┌───────────────────────────────┐
    │  ImageRender.render(context)  │  Jinja2-шаблон → HTML
    └───────────────┬───────────────┘
                    ▼
    ┌───────────────────────────────┐
    │  Renderer.render_html(...)    │  Playwright Chromium · скриншот
    └───────────────┬───────────────┘
                    ▼
    render_cache.set(key, bytes) ──▶ Ответ · X-Cache: miss
```

Два кэша ускоряют работу:

| Кэш | Ключ | Что хранит |
|-----|------|------------|
| `ImageRender._cache` | id шаблона | скомпилированное окружение Jinja2 |
| `render_cache` | sha256(шаблон + контекст + формат + качество) | готовые байты картинки (LRU) |

**Почему это быстро?** Скриншот — дорогая операция, но повторный идентичный
запрос отдаётся из кэша за миллисекунды. Заголовок `X-Cache` показывает, по
какому пути прошёл запрос.

---
## 📁 Структура

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
│   └── templates/             # ← ВСЕ ШАБЛОНЫ ЗДЕСЬ
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

**С чего читать:** `services/template.py:discover()` →
`schemas/template.py:TemplateManifest` → `services/render.py:ImageRender.render()` →
`services/render.py:Renderer.render_html()`.

---

## 📦 Требования

- Python `>= 3.14`
- [`uv`](https://docs.astral.sh/uv/) (рекомендуется) или `pip`
- Chromium из состава Playwright

```bash
uv sync                              # поставить зависимости
uv run playwright install chromium   # один раз скачать браузер
uv sync --group dev                  # + pytest для тестов
```

Зависимости: `fastapi`, `jinja2`, `playwright`, `pydantic-settings`,
`uvicorn`, `loguru`, `kubiks`.

---

## 🚀 Быстрый старт

```bash
git clone <repo> HTMLshot && cd HTMLshot
uv sync
uv run playwright install chromium
uv run uvicorn htmlshot.main:app --host 127.0.0.1 --port 8000 --reload
```

Открой **http://127.0.0.1:8000/docs** — там интерактивный Swagger UI.

```bash
# 1. какие шаблоны доступны?
curl http://127.0.0.1:8000/templates

# 2. посмотреть HTML (мгновенно, без скриншота)
curl -X POST "http://127.0.0.1:8000/preview?template=profile_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"кубик","avatar":"avatar.png"}'

# 3. отрендерить картинку
curl -X POST "http://127.0.0.1:8000/render?template=profile_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"кубик","usertitle":"тест","avatar":"avatar.png","background":"bg.png","season_title":"Сезон 1","common_stats":[],"season_stats":[]}' \
  --output card.webp
```

Из Python:

```python
import httpx

resp = httpx.post(
    "http://127.0.0.1:8000/render",
    params={"template": "profile_card"},
    json={"username": "кубик", "avatar": "avatar.png"},
)
print(resp.headers["X-Cache"])   # miss при первом вызове, потом hit
open("card.webp", "wb").write(resp.content)
```

---

## ⚙️ Настройка

Настройки живут в `src/htmlshot/config.py` (`pydantic-settings`, неизменяемый
экземпляр кэшируется в `load_settings()`). Все переменные с префиксом
`HTMLSHOT_` читаются из окружения или из файла `.env` в корне проекта.

| Переменная | По умолчанию | Смысл |
|------------|---------------|-------|
| `HTMLSHOT_TITLE` | `HTMLShot` | Заголовок в OpenAPI / `/docs` |
| `HTMLSHOT_HOST` | `127.0.0.1` | Адрес привязки (в Docker — `0.0.0.0`) |
| `HTMLSHOT_PORT` | `8000` | HTTP-порт, от 1 до 65535 |

```ini
# .env
HTMLSHOT_TITLE=HTMLShot
HTMLSHOT_HOST=0.0.0.0
HTMLSHOT_PORT=8000
```

Валидация строгая: нечисловой или выходящий за диапазон порт приводит к понятной
ошибке Pydantic на старте, а не к молчаливому биндингу не на тот сокет.

---

## 🌐 API

`template`, `context`, `html`, `width` и `height` передаются **query-параметрами**;
`context` — JSON-объект в теле запроса.

### `GET /templates`

Список всех найденных шаблонов.

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
      "description": "Приветствует пользователя по имени"
    }
  ]
}
```

### `POST /preview?template={id}`

Рендерит шаблон и возвращает **HTML вместо картинки** — браузер не запускается,
поэтому это самый быстрый способ отладки.

```bash
curl -X POST "http://127.0.0.1:8000/preview?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"кубик","vip":true}'
```

### `POST /render?template={id}`

Основной эндпоинт: рендер → скриншот → байты картинки.

```bash
curl -X POST "http://127.0.0.1:8000/render?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"кубик","vip":true}' --output card.webp
```

| Заголовок ответа | Значение |
|------------------|----------|
| `Content-Type: image/webp` | формат из `default_format` (`webp` по умолчанию, либо `png` / `jpeg`) |
| `X-Cache: hit` | отдано из LRU-кэша, рендера не было |
| `X-Cache: miss` | только что отрендерено и положено в кэш |

### `POST /render/raw?html=...&width=...&height=...`

Рендерит произвольный HTML без шаблона и без кэша. Всегда WebP.

```bash
curl -X POST "http://127.0.0.1:8000/render/raw?html=<h1>Привет</h1>&width=640&height=360" \
  --output raw.webp
```

### Коды ответа

| Код | Когда |
|-----|-------|
| `200` | успех |
| `404` | неизвестный `template` |
| `422` | нет параметра `template`, нет JSON-тела или неверные `width`/`height` |

---
## 🎨 Создание своего шаблона

Это самое главное в HTMLShot. Шаблон — это просто **папка**:
ни базы данных, ни регистрации, ни кода.

```text
src/htmlshot/templates/
└── hello_card/                 <- имя папки = id шаблона
    ├── manifest.json           <- необязательно, но рекомендуется
    ├── index.html              <- входной файл (Jinja2)
    ├── style.css               <- стили
    └── avatar.png              <- ассеты лежат рядом с шаблоном
```

`TemplateService(PROJECT_ROOT / "src" / "htmlshot" / "templates").discover()`
сканирует корневой каталог **один раз при старте** и регистрирует все
валидные подпапки.

> 💡 `id` — это всегда имя папки. В `manifest.json` его задавать не нужно,
> сервис перезаписывает его сам.

---

### 1️⃣ Шаг 1 — создаём папку

```bash
mkdir -p src/htmlshot/templates/hello_card
```

### 2️⃣ Шаг 2 — `manifest.json`

Говорит сервису, какой файл рендерить, какого размера картинка и в каком
формате её сохранять.

```json
{
  "name": "Hello card",
  "entrypoint": "index.html",
  "viewport": { "width": 400, "height": 200 },
  "description": "Приветствует пользователя по имени",
  "default_format": "png",
  "default_quality": 90
}
```

| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `id` | `str` | *имя папки* | Проставляется автоматически. Используется в `?template=` |
| `name` | `str` | `""` | Имя для человека, видно в `GET /templates` |
| `entrypoint` | `str` | `index.html` | Jinja2-файл внутри папки |
| `viewport.width` | `int` | `800` | Ширина скриншота в px, должна быть `> 0` |
| `viewport.height` | `int` | `600` | Высота скриншота в px, должна быть `> 0` |
| `description` | `str` | `""` | Видно в `GET /templates` |
| `default_format` | `str\|null` | `null` → `webp` | `webp`, `png` или `jpeg` |
| `default_quality` | `int\|null` | `null` → `70` | Качество для сжимаемых форматов |

> ⚠️ Некорректный манифест (битый JSON, `viewport: {"width": 0}`, отрицательная
> высота) приводит к тому, что сервис **пропустит шаблон** с предупреждением —
> остальные шаблоны продолжат работать.

**А если манифеста нет?** Всё равно заработает: сервис возьмёт первый файл
`*.htm*` в папке и использует `name = <имя папки>`, `viewport = 800x600`, без
формата и качества. Отлично подходит для быстрого прототипа, но для реальной
работы манифест лучше добавить.

### 3️⃣ Шаг 3 — входной HTML

Подойдёт любой файл `*.htm*`: `index.html`, `index.htm`, `card.htm`,
`profile.html`. Это **Jinja2-шаблон**, который рендерится с твоим
JSON-контекстом.

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="./style.css">
</head>
<body>
  <div class="card">
    <img class="avatar" src="{{ avatar }}">
    <div class="hello">Привет, {{ username | default("странник") }}!</div>
    {% if vip %}<div class="badge">VIP</div>{% endif %}
  </div>
</body>
</html>
```

🔑 **Золотое правило:** всегда подключай
`<link rel="stylesheet" href="./style.css">`. Браузер грузит файл из папки
шаблона, поэтому без него картинка будет без стилей.

Как контекст превращается в переменные:

```text
Тело POST  {"username": "кубик", "vip": true}
              ↓
Jinja       {{ username }}  →  "кубик"
            {% if vip %}     →  true  (блок отрисуется)
```

`ImageRender.render()` только подставляет переменные из JSON-контекста — таблица
стилей подключается из входного HTML обычным относительным путём.

---
### 4️⃣ Шаг 4 — CSS

`style.css` лежит рядом с входным HTML, и грузит его сам Chromium через
`file://` — относительные `url(...)` внутри разрешаются от CSS-файла, поэтому
шрифты и картинки держи в той же папке.

```css
@font-face {
  font-family: "Impact";
  src: url("Impact.ttf");          /* грузит браузер */
}

body {
  margin: 0;
  width: 400px;                    /* совпадай с viewport! */
  height: 200px;
  display: flex;                   /* flexbox / grid тоже работают */
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

**Правила для ассетов:**

| Ссылка | Результат |
|--------|-----------|
| `url("bg.png")` | грузится из папки шаблона браузером |
| `url("Impact.ttf")` | то же — без base64, HTML остаётся маленьким |
| `url("https://...")` | скачивается браузером во время скриншота |
| `url("data:...")` | используется как есть |
| файла нет | битая картинка в результате |

> 🖼 Картинки, переданные **в JSON-контексте, тоже грузит браузер**: положи файл
> рядом с входным HTML и укажи относительный путь — Playwright разрешит его через
> `base_path`.

### 5️⃣ Шаг 5 — рестарт и отладка через `/preview`

`discover()` работает только на старте, поэтому перезапусти сервер:

```bash
uv run uvicorn htmlshot.main:app --reload
curl http://127.0.0.1:8000/templates | python3 -m json.tool
```

Шаблон должен появиться в списке. Дальше доводи дизайн через `/preview` —
он возвращает HTML, **браузер не запускается**, поэтому всё мгновенно:

```bash
curl -X POST "http://127.0.0.1:8000/preview?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"кубик","avatar":"avatar.png","vip":true}'
```

### 6️⃣ Шаг 6 — рендерим картинку

```bash
curl -X POST "http://127.0.0.1:8000/render?template=hello_card" \
  -H "Content-Type: application/json" \
  -d '{"username":"кубик","avatar":"avatar.png","vip":true}' \
  --output hello.png && file hello.png
```

Повтори запрос — в ответе будет заголовок `X-Cache: hit`. 🎉

### 7️⃣ Шаг 7 — копируем

Скопируй папку, переименуй — готово. Новая папка = новый id шаблона.

```bash
cp -r src/htmlshot/templates/hello_card src/htmlshot/templates/goodbye_card
# затем поправь manifest.json -> "name": "Goodbye card"
```

---
### 🧠 Продвинутый Jinja2

Циклы, условия и фильтры работают как в любом Jinja2-шаблоне:

```html
<h2>{{ season_title | upper }}</h2>

{% for s in common_stats %}
  <div class="stat">
    <span class="icon">{{ s.icon }}</span>
    <b>{{ s.value }}</b>
    <i>{{ s.label }}</i>
  </div>
{% else %}
  <p class="muted">Статистики пока нет</p>
{% endfor %}

{% if vip %}<div class="badge">VIP</div>{% endif %}
{{ comment | e }}   {# экранируй недоверенный ввод! #}
```

Окружение Jinja2 используется с настройками по умолчанию, поэтому
**недоверенный ввод экранируй через `|e`**.

### 🚧 Правила поиска шаблонов и грабли

Как ведёт себя `TemplateService.discover()`:

| Ситуация | Результат |
|----------|-----------|
| Файл (не папка) в корне templates | игнорируется |
| Валидный `manifest.json` + существующий entrypoint | ✅ зарегистрирован |
| Битый `manifest.json` / `viewport <= 0` | ⚠️ пропущен, в лог ошибка |
| Файла entrypoint нет | ⚠️ пропущен, в лог предупреждение |
| Нет `manifest.json` | берётся первый `*.htm*`, затем `index.html` |
| `discover()` вызван повторно | реестр сначала очищается |

Частые ошибки:

| Симптом | Причина |
|---------|---------|
| Шаблона нет в `/templates` | не то имя папки или манифест отклонён |
| Картинка без стилей | забыл `<link rel="stylesheet" href="./style.css">` |
| Картинка обрезана | размер `body` в CSS не совпадает с `viewport` |
| Битая картинка | путь в `url()` считается от **CSS-файла**, а не от входного HTML |
| 404 после добавления папки | сервер не перезапущен — хот-релоада шаблонов нет |

---

## ⚙️ Конвейер подробно

**1 · Находим шаблон** — `api/render.py` обращается к
`request.app.state.templates.get(template_id)` и отдаёт `404`, если шаблона нет.

**2 · Проверяем кэш** — `make_cache_key(template_id, context, format, quality)`
считает SHA-256 от канонического JSON; при попадании ответ возвращается сразу.

**3 · Рендерим HTML** — `ImageRender.for_template(manifest)` возвращает
закэшированный синглтон на каждый id (скомпилированное окружение Jinja2
переиспользуется). `.render(context)` копирует твой словарь (никогда не
мутирует его) и вызывает `template.render(**ctx)`.

**4 · Делаем скриншот** — `Renderer.render_html()`:

```text
new_page(viewport={width, height})
  → page.goto(base_path.as_uri())      # чтобы работали относительные пути
  → page.set_content(html)
  → page.wait_for_load_state("load")
  → ждём загрузки всех <img>
  → page.screenshot(full_page=False, type=format, quality=quality)
```

**5 · Кэшируем и отвечаем** — байты уходят в LRU, а ответ возвращается
с заголовком `X-Cache: miss`.

Chromium запускается один раз в lifespan с продакшн-флагами:

```text
--disable-dev-shm-usage   --force-color-profile=srgb
--hide-scrollbars         --font-render-hinting=none
```

---

## 💾 Кэширование

**1 · LRU картинок** — `services/cache.py`

```python
make_cache_key(template_id, context, image_format, quality) -> str  # sha256 hex
```

- Канонический JSON с `sort_keys=True` → порядок ключей не важен.
- `ensure_ascii=False, default=str` → несериализуемые значения не ломают сервис.
- `RenderCache(max_entries=128, max_bytes=256 МБ)` — честный LRU на
  `OrderedDict`: `get()` переносит запись в конец, а `set()` вытесняет самые
  старые записи, пока не выполнены оба лимита.

**2 · Окружения Jinja** — `ImageRender.for_template()` хранит по одному
скомпилированному шаблону на id в словаре класса, парсинг происходит один раз.

> ♻️ Кэш живёт в процессе. Несколько воркеров → у каждого свой браузер и свой
> кэш.

---
## 🧪 Тесты

```bash
uv sync --group dev
uv run pytest -v
uv run pytest tests/test_template_service.py -v   # один файл
```

| Фикстура | Что делает |
|----------|-----------|
| `make_template()` | собирает временную папку шаблона (`index.htm` + `style.css` + манифест `320x180`) и заново запускает `discover()` |
| `client` | `TestClient` с заглушкой lifespan (браузер не запускается) |
| `renderer_stub` | подменяет `Renderer.render_html`, записывает вызовы, возвращает `b"fake-image-bytes"` |
| `clear_global_caches` | autouse — чистит `render_cache` и `ImageRender._cache` до и после каждого теста |

Покрыто: валидация манифестов, запасные пути при поиске шаблонов, подстановка
контекста, ключи кэша, вытеснение LRU, разбор настроек и все эндпоинты.

---

## 🩺 FAQ

<details>
<summary>404 <code>Template X not found</code></summary>

id шаблона — это имя папки. Проверь `GET /templates`: если шаблона там нет,
значит `discover()` его пропустил (битый `manifest.json`, `viewport <= 0` или
отсутствующий файл entrypoint). Смотри предупреждения loguru на старте.
</details>

<details>
<summary>Картинка без стилей</summary>

Ты забыл `<link rel="stylesheet" href="./style.css">` либо файла `style.css` нет
в папке шаблона. Проверь через `POST /preview`: в возвращённом HTML видно
настоящий `href`.
</details>

<details>
<summary><code>BrowserRender.start() must be called first</code></summary>

`Renderer.start()` запускается в lifespan FastAPI. Либо ты обошёл lifespan, либо
не запустился Playwright. Смотри логи.
</details>

<details>
<summary>Playwright: не найден исполняемый файл браузера</summary>

```bash
uv run playwright install chromium
uv run playwright install-deps chromium   # системные библиотеки на Linux
```
</details>

<details>
<summary>Не отображаются картинки или шрифты</summary>

Указывай относительные пути: в CSS `url()` они считаются от CSS-файла, в
JSON-контексте — от входного HTML (`base_path`). Файлы должны лежать внутри
папки шаблона — все ассеты грузит сам браузер.
</details>

<details>
<summary>Первый рендер медленный</summary>

Холодный старт Chromium плюс компиляция Jinja. Повторные одинаковые запросы
отдаются из LRU-кэша за миллисекунды — смотри заголовок `X-Cache`.
</details>

<details>
<summary>Добавил шаблон, а сервер его не видит</summary>

`discover()` работает только на старте. Перезапусти сервер.
</details>

---.
