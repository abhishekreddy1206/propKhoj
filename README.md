# propKhoj

## Overview

propKhoj is an AI-powered real estate property search platform that combines conversational AI with vector-similarity search to help users find properties. Users interact with a chatbot that understands natural-language queries, performs RAG (Retrieval-Augmented Generation) against a PostgreSQL/pgvector property database, and returns relevant listings alongside AI-generated responses.

## Architecture

```
frontend/          React 19 + TypeScript + Tailwind CSS (CRA)
backend/           Django 4.2 REST API
  api/             Core app: models, views, serializers, managers, analytics, tests
  propkhoj/        Django project settings, root URL config, auth views
docker-compose.base.yml   Orchestrates backend (port 8000) and frontend (port 3000/80)
```

### Tech Stack

| Layer        | Technology                                                  |
|--------------|-------------------------------------------------------------|
| Frontend     | React 19, TypeScript, Tailwind CSS, Framer Motion, Axios    |
| Backend      | Django 4.2, Django REST Framework, dj-rest-auth, allauth    |
| Database     | PostgreSQL with pgvector extension                          |
| AI           | OpenAI API (gpt-4o-mini for chat, text-embedding-3-small for embeddings) |
| Auth         | Token auth, social OAuth (Google, Facebook, GitHub)         |
| Geocoding    | Google Maps Geocoding API                                   |
| Server       | Gunicorn (backend), Nginx (frontend static serving + API proxy) |

### Data Models

| Model           | Purpose                                                       |
|-----------------|---------------------------------------------------------------|
| User            | Extended AbstractUser with user_type (buyer/seller/admin/agent), phone, address, profile image |
| Address         | Geocoded address with Google Maps verification, lat/lng       |
| Property        | Core listing: pricing, details, area, amenities, 1536-dim vector embedding, content hash for smart re-embedding |
| PropertyImage   | Image records with type/ordering                              |
| PropertyType    | Lookup table for property categories                          |
| ListingStatus   | Lookup table for listing states                               |
| Currency        | Multi-currency support                                        |
| Amenity         | Property amenity catalog                                      |
| Conversation    | Chat session tied to a user                                   |
| ChatMessage     | Individual message with sender (user/bot), feedback tracking, linked properties |

### API Routes

**Authentication** (prefix: `/auth/`)
- `POST /auth/` -- email/password login (dj-rest-auth)
- `POST /auth/registration/` -- user registration
- `GET /auth/csrf/` -- fetch CSRF token
- `GET /auth/{provider}/init/` -- initiate social OAuth (google, facebook, github)
- `POST /auth/{provider}/callback/` -- complete social OAuth

**Properties** (prefix: `/api/properties/`)
- Standard CRUD via DRF ModelViewSet (read: public, write: authenticated)
- `GET /api/properties/search/?q=` -- text-based property search (title, city, state, zip)

**Chat** (prefix: `/api/chats/`)
- `POST /api/chats/chat/` -- send message, get AI response with hybrid RAG property results
- `GET /api/chats/sample-prompts/` -- AI-generated sample prompts (optional `conversation_id`)
- `POST /api/chats/feedback/<chat_id>/` -- submit like/dislike feedback on a bot message

**Conversations** (prefix: `/api/conversations/`)
- Standard CRUD via DRF ModelViewSet (scoped to authenticated user)

**Users & Profile** (prefix: `/api/`)
- `/api/users/` -- user CRUD, login, `/me` endpoint
- `/api/profile/me/` -- get authenticated user profile
- `/api/profile/update_profile/` -- update profile

**Analytics** (admin-only, prefix: `/api/`)
- `GET /api/admin/analytics/` -- rendered analytics dashboard (staff only)
- `GET /api/analytics/metrics/` -- conversation metrics (totals, averages, feedback, peak hours)
- `GET /api/analytics/topics/` -- AI-analyzed topic trends
- `GET /api/analytics/properties/` -- property interest analysis
- `GET /api/analytics/intents/` -- AI-generated user intent clusters
- `GET /api/analytics/summary/` -- AI-generated executive summary

### Frontend Routes

| Path        | Component        | Access          |
|-------------|------------------|-----------------|
| `/`         | HomePage         | Public          |
| `/login`    | LoginPage        | Public          |
| `/register` | RegisterPage     | Public          |
| `/features` | FeaturesPage     | Public          |
| `/chat`     | ChatBot          | Authenticated   |
| `/admin`    | AdminDashboard   | Admin only      |
| `/profile`  | ProfilePage      | Public          |

### Key Workflows

**Chat with Hybrid RAG Search:**
1. User sends a message via `POST /api/chats/chat/` (max 5000 characters, rate-limited to 60/hour)
2. Backend uses OpenAI function calling to extract structured filters (price range, bedrooms, city, property type) from the query
3. Backend generates an embedding of the query using text-embedding-3-small
4. pgvector cosine-distance search finds the top 5 similar properties, further filtered by the extracted structured filters
5. Property text representations are injected as context into the conversation
6. Full conversation history + system prompt + property context are sent to gpt-4o-mini
7. Bot response and serialized matching properties are returned to the frontend

**Property Embedding Generation:**
- On `Property.save()`, a text representation is built from title, description, type, location, price, amenities, tags, and more
- A SHA-256 content hash is computed; the embedding is only regenerated if the hash has changed
- Embeddings are generated via OpenAI text-embedding-3-small (1536 dimensions)
- Bulk re-embedding available via `python manage.py regenerate_embeddings` (supports `--force` and `--batch-size` flags)

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Environment variables configured in `backend/.env` and `frontend/.env`

### Required Environment Variables

The backend requires the following variables in `backend/.env`:
- `DJANGO_SECRET_KEY` -- Django secret key
- `DJANGO_DEBUG` -- debug mode flag
- `DJANGO_ALLOWED_HOSTS` -- comma-separated allowed hostnames
- `DATABASE_URL` -- PostgreSQL connection string (must have pgvector extension)
- `OPENAI_API_KEY` -- OpenAI API key
- `GOOGLE_MAPS_API_KEY` -- Google Maps Geocoding API key
- `CORS_ALLOWED_ORIGINS` -- comma-separated allowed CORS/CSRF origins
- `OAUTH_REDIRECT_URI` -- OAuth callback redirect URL
- Social OAuth credentials (Google, Facebook, GitHub client IDs and secrets)

The frontend requires:
- `REACT_APP_API_URL` -- backend API base URL (defaults to `http://localhost:8000`)

### Setup

1. **Build the Docker images**

   ```bash
   docker-compose -f docker-compose.base.yml build --no-cache
   ```

2. **Start the application**

   ```bash
   docker-compose -f docker-compose.base.yml up
   ```

   This starts:
   - Backend on port **8000** (runs migrations automatically, then starts Gunicorn with 3 workers)
   - Frontend on port **3000** (Nginx serving the built React app with SPA fallback and API proxy)
   - Health checks run on both services

3. **Access the Django shell**

   ```bash
   docker-compose -f docker-compose.base.yml run backend python manage.py shell
   docker-compose -f docker-compose.base.yml run backend bash
   ```

4. **Load sample property data**

   ```bash
   docker-compose -f docker-compose.base.yml run backend python manage.py add_sample_listings
   ```

5. **Regenerate property embeddings**

   ```bash
   docker-compose -f docker-compose.base.yml run backend python manage.py regenerate_embeddings
   # Use --force to regenerate all, --batch-size N to control batch size
   ```

### Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

**Frontend:**
```bash
cd frontend
npm install
npm start
```

### Running Tests

**Backend:**
```bash
cd backend
python manage.py test api
```

**Frontend:**
```bash
cd frontend
npm test
```

## Security

- CORS and CSRF origins are environment-driven (not hardcoded)
- Permission classes enforced on all viewsets (IsAuthenticated for chat/conversations/profile, IsAuthenticatedOrReadOnly for properties)
- Rate throttling via DRF ScopedRateThrottle (60 chat messages/hour, 10 login attempts/minute)
- Embedding vectors excluded from API serializer responses
- Message length validation (5000 character limit)
- Security headers enabled (HSTS, X-Frame-Options DENY, XSS filter, content-type nosniff)
- CSRF cookie is Secure in production, SameSite=Lax

## Logging

Logs are written to `backend/logs/` using RotatingFileHandler (10 MB per file, 5 backups):
- `app.log` -- general application logs
- `error.log` -- error-level logs
- `access.log` -- HTTP request access logs (JSON format)
- `chat.log` -- chat-specific logs (messages sent, AI responses)

## Contributing

We welcome contributions! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

