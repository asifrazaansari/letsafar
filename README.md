# رِحلة — Rihla

**Sacred Travel Intelligence Platform**

A full-stack travel planning platform built for sacred journeys — Hajj, Umrah,
Ziyarat, and beyond. Combines modern AI with deep cultural and spiritual awareness.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), Tailwind CSS, React Flow, NextAuth.js v5 |
| Backend | Python 3.13, FastAPI, Motor (async MongoDB), python-socketio |
| Database | MongoDB Atlas (primary), Redis (cache/sessions) |
| AI | LangGraph, OpenAI GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Flash |
| Auth | Google OAuth 2.0 → JWT (Rihla-issued) |
| Real-time | Socket.IO (trip collaboration, live comments) |

---

## Quick Start

### Prerequisites
- Python 3.12+, Node.js 20+
- MongoDB Atlas account (or local MongoDB)
- Google OAuth credentials
- API keys for at least one AI provider (OpenAI / Anthropic / Google AI)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in your credentials
cp ../infra/.env.example .env
# Edit .env: MONGODB_URI, JWT_SECRET, GOOGLE_CLIENT_ID, AI keys

uvicorn app.main:app --reload
# → http://localhost:8000
# → /docs for Swagger UI
```

### 2. Frontend

```bash
cd frontend
npm install

# Copy and fill
cp ../infra/.env.example .env.local
# Edit .env.local: NEXTAUTH_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

npm run dev
# → http://localhost:3000
```

### 3. Infrastructure (optional — Docker)

```bash
# Start MongoDB + Redis via Docker
docker compose -f infra/docker-compose.yml up mongo redis -d
```

---

## Features

### Phase 1 — Foundation ✅
- Google OAuth sign-in → Rihla JWT
- 3 aesthetic themes: Sacred Night (default), Desert Parchment, Glacier Minimal
- Full Trip CRUD with tags, budget, status, visibility
- Recursive destination node tree (city → place → activity → stay → transit)
- Share system with role-based access (owner / editor / commenter / viewer)
- Public explore feed with trip forking
- Cost summary endpoint

### Phase 2 — Visualization ✅
- **React Flow canvas** — interactive node map with drag/pan/zoom
- **Gantt Timeline** — visual date-based trip timeline
- **Cost Splitter** — split trip costs among travellers (equal or custom %)
- **Share Modal** — invite collaborators by email, manage roles

### Phase 3 — Real-time ✅
- **Socket.IO** — live comment streaming on trip rooms
- **Presence indicators** — see who's viewing a trip live
- **Optimistic node updates** — broadcast changes to co-viewers

### Phase 4 — AI Intelligence ✅
- **6 specialist agents** via LangGraph:
  1. 🗺 **Planner** — analyses trip, delegates to specialists
  2. 🔍 **Research** — discovers places, attractions, local info
  3. 🕌 **Sacred** — Islamic heritage, prayer times, halal guide
  4. ✈️ **Logistics** — routing, timing, transportation
  5. 💰 **Cost** — budget estimation and splitting
  6. ✍️ **Writer** — synthesises into beautiful narrative
- **MCP-style tools**: `get_trip_tree`, `update_node`, `search_place`, `get_prayer_times`, `calculate_cost_split`, `get_weather`
- **SSE streaming** — real-time agent token streaming to frontend
- **AI Panel** — interactive UI with preset quick actions

---

## Themes

| Theme | Style | Fonts |
|-------|-------|-------|
| Sacred Night | Dark ink `#0f0c08` + gold `#c9a84c` | Cinzel + Cormorant Garamond |
| Desert Parchment | Warm cream + terracotta | Playfair Display + Lora |
| Glacier Minimal | Cool slate + steel blue | DM Serif Display + Inter |

---

## API Endpoints

```
POST /auth/google          Google id_token → Rihla JWT pair
POST /auth/refresh         Rotate refresh token

GET  /users/me             Current user profile
PUT  /users/me             Update theme, AI model preference

GET  /trips                List trips (own + shared)
POST /trips                Create trip
GET  /trips/:id            Trip detail with collaborators
PUT  /trips/:id            Update trip
DELETE /trips/:id          Delete trip

GET  /trips/:id/nodes      Full recursive node tree
POST /trips/:id/nodes      Add root or child node
PUT  /nodes/:id            Update node
DELETE /nodes/:id          Delete node + subtree
PATCH /nodes/:id/move      Reorder/reparent node

POST /trips/:id/share      Invite collaborator by email
PUT  /trips/:id/share/:uid Change role
DELETE /trips/:id/share/:uid Revoke access
POST /trips/:id/share/accept Accept invite

GET  /trips/:id/comments   All comments (enriched)
POST /nodes/:id/comments   Add comment
DELETE /comments/:id       Delete comment

GET  /trips/:id/costs      Cost summary + per-person breakdown

GET  /explore              Public trip feed
POST /trips/:id/fork       Deep-copy a public trip

POST /ai/enhance           Run 6-agent pipeline (SSE stream)
POST /ai/chat              Quick chat with Writer agent (SSE)

GET  /health               Health check
```

---

## Socket.IO Events

```
Namespace: /trips  (path: /ws)

Client → Server:
  join_trip   { trip_id }
  leave_trip  { trip_id }
  send_comment { trip_id, node_id, text }
  node_updated { trip_id, node_id, changes }

Server → Client:
  new_comment  { id, trip_id, node_id, user_name, text, created_at }
  user_joined  { user_id, user_name }
  user_left    { user_id, user_name }
  node_changed { trip_id, node_id, changes }
```

---

## Environment Variables

See [`infra/.env.example`](infra/.env.example) for the full list.

**Minimum required for dev:**
```env
MONGODB_URI=mongodb+srv://...        # MongoDB Atlas URI
JWT_SECRET=<32-byte base64 secret>
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
NEXTAUTH_SECRET=<32-byte base64 secret>
```

**For AI features:**
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=AIza...
```
