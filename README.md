# propKhoj

## Overview

propKhoj is an AI-powered real estate property search platform that combines conversational AI with vector-similarity search to help users find properties. Users interact with a chatbot that understands natural-language queries, performs RAG (Retrieval-Augmented Generation) against a PostgreSQL/pgvector property database, and returns relevant listings alongside AI-generated responses.

## Architecture

```
frontend/          React 19 + TypeScript + Tailwind CSS (CRA)
backend/           Django 4.2 REST API
  api/             Core app: models, views, serializers, managers, analytics
  propkhoj/        Django project settings, root URL config, auth views
docker-compose.base.yml   Orchestrates backend (port 8000) and frontend (port 3000)
```

### Tech Stack

| Layer        | Technology                                                  |
|--------------|-------------------------------------------------------------|
| Frontend     | React 19, TypeScript, Tailwind CSS, Framer Motion, Axios    |
| Backend      | Django 4.2, Django REST Framework, dj-rest-auth, allauth    |
| Database     | PostgreSQL with pgvector extension                          |
| AI           | OpenAI API (gpt-4o-mini for chat, text-embedding-ada-002 for embeddings) |
| Auth         | Token auth, social OAuth (Google, Facebook, GitHub)         |
| Storage      | Supabase (property images)                                  |
| Geocoding    | Google Maps Geocoding API                                   |
| Server       | Gunicorn (production), Nginx (frontend static serving)      |

### Data Models

| Model           | Purpose                                                       |
|-----------------|---------------------------------------------------------------|
| User            | Extended AbstractUser with user_type (buyer/seller/admin/agent), phone, address, profile image |
| Address         | Geocoded address with Google Maps verification, lat/lng       |
| Property        | Core listing: pricing, details, area, amenities, 1536-dim vector embedding for similarity search |
| PropertyImage   | Image records stored in Supabase with type/ordering           |
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
- Standard CRUD via DRF ModelViewSet
- `GET /api/properties/search/?q=` -- text-based property search

**Chat** (prefix: `/api/chats/`)
- `POST /api/chats/chat/` -- send message, get AI response with RAG property results
- `GET /api/chats/sample-prompts/` -- AI-generated sample prompts (optional `conversation_id`)
- `POST /api/chats/feedback/<chat_id>/` -- submit like/dislike feedback on a bot message

**Conversations** (prefix: `/api/conversations/`)
- Standard CRUD via DRF ModelViewSet

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

**Chat with RAG Search:**
1. User sends a message via `POST /api/chats/chat/`
2. Backend generates an embedding of the query using OpenAI text-embedding-ada-002
3. pgvector cosine-distance search finds the top 5 similar properties
4. Full conversation history + system prompt are sent to gpt-4o-mini
5. Bot response and matching properties are returned to the frontend

**Property Embedding Generation:**
- On `Property.save()`, a text representation is built from title, description, type, location, price, amenities, and tags
- An embedding is generated via OpenAI and stored in the 1536-dimension vector field
- Bulk embedding updates are available via `PropertyManager.bulk_update_embeddings()`

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Environment variables configured in `backend/.env` and `frontend/.env`

### Required Environment Variables

The backend requires the following variables in `backend/.env`:
- `DJANGO_SECRET_KEY` -- Django secret key
- `DJANGO_DEBUG` -- debug mode flag
- `DATABASE_URL` -- PostgreSQL connection string (must have pgvector extension)
- `OPENAI_API_KEY` -- OpenAI API key
- `GOOGLE_MAPS_API_KEY` -- Google Maps Geocoding API key
- Social OAuth credentials (Google, Facebook, GitHub client IDs and secrets)
- Supabase credentials (for image storage)

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
   - Backend on port **8000** (runs migrations automatically, then starts Django dev server)
   - Frontend on port **3000** (Nginx serving the built React app)

3. **Access the Django shell**

   ```bash
   docker-compose -f docker-compose.base.yml run backend python manage.py shell
   docker-compose -f docker-compose.base.yml run backend bash
   ```

4. **Load sample property data**

   ```bash
   docker-compose -f docker-compose.base.yml run backend python manage.py add_sample_listings
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

## Logging

Logs are written to `backend/logs/`:
- `app.log` -- general application logs
- `error.log` -- error-level logs
- `access.log` -- HTTP request access logs (JSON format)
- `chat.log` -- chat-specific logs (messages sent, AI responses)

## Contributing

We welcome contributions! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any inquiries or support, please contact [support@propkhoj.com](mailto:support@propkhoj.com).