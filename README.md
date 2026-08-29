# Ecommerce Post Automation Engine

Extract product data from e-commerce product URLs (Daraz, Bikroy, or any page) into clean, structured posts — with a persistent post library, optional WordPress publishing, and a browsable web UI.

Stack: **FastAPI** + **Playwright** + **BeautifulSoup** + **SQLModel**/**PostgreSQL** on the backend, **React** + **Vite** + **Tailwind** + **shadcn/ui** on the frontend.

## Features

- **One-click extract** — paste a product URL and get structured data (title, price, images, seller info, description) instantly.
- **Source adapters** — dedicated scrapers for Daraz and Bikroy, with a generic fallback for other pages.
- **Persistent post library** — every scrape is saved to PostgreSQL as a post you can list, view, and delete.
- **Optional WordPress publish** — extract + publish pushes the post (with downloaded media) to a WordPress site via its REST API.
- **Rich content rendering** — builds a clean HTML gallery + seller card + description body for each post.
- **Web UI** — React frontend with a scrape form, live preview, a browsable posts list, post detail pages, a full-screen image lightbox, and light/dark themes.
- **Media handling** — scraped product images are downloaded and cached locally before publishing.

## Architecture

```
┌──────────────┐   /api   ┌─────────────────────────────────────────┐
│  React (Vite) │ ───────▶ │  FastAPI  ──▶ Adapters (Daraz/Bikroy)  │
│  /posts, /    │ ◀─────── │           ──▶ SQLModel / PostgreSQL    │
│  lightbox     │          │           ──▶ WPPublisher (optional)   │
└──────────────┘          └─────────────────────────────────────────┘
```

### Backend layout

- `src/scrape_engine/scrapers/` — per-source scrapers + generic fallback
- `src/scrape_engine/publishers/wp_publisher.py` — WordPress REST publish + content rendering
- `src/scrape_engine/models/` — SQLModel `Post` table + Pydantic schemas
- `src/scrape_engine/routers/posts.py` — post CRUD endpoints
- `src/scrape_engine/db.py` — async engine/session + `init_db()`

### Frontend routes

- `/` — scrape form + live preview + recent posts
- `/posts` — posts list with delete
- `/posts/:id` — post detail with image lightbox

## API

| Method | Path                  | Description                            |
| ------ | --------------------- | -------------------------------------- |
| `POST` | `/scrape`             | Extract a product (optional publish)   |
| `GET`  | `/posts`              | List persisted posts                   |
| `GET`  | `/posts/count`        | Total persisted posts                  |
| `POST` | `/posts`              | Create a post                          |
| `GET`  | `/posts/{id}`         | Get a single post                      |
| `DELETE` | `/posts/{id}`       | Delete a post                          |
| `GET`  | `/health`             | Liveness check                         |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+ (for the frontend)
- PostgreSQL (for post persistence)

### Backend

```bash
uv sync                 # install Python deps
cp .env.example .env     # review configuration
uv run uvicorn scrape_engine.main:app --reload --port 8000
```

`DATABASE_URL` defaults to `postgresql+psycopg://scrape:scrape_secret@127.0.0.1:5432/scrape_engine` (see `src/scrape_engine/db.py`).

Install Playwright browsers once:

```bash
uv run playwright install chromium
```

### Frontend

```bash
cd web
npm install
npm run dev             # http://localhost:5173  (proxies /api -> 127.0.0.1:8000)
```

### WordPress publishing (optional)

Set `WP_BASE_URL`, `WP_USERNAME`, and `WP_APPLICATION_PASSWORD` in `.env` (generate an Application Password in WordPress → Users → Application Passwords). Without these, publishing reports that WordPress is not configured; extraction/persistence still works.
