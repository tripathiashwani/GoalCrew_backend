# GoalCrew Backend

An enterprise-grade social accountability API built with **FastAPI**, structured around **Domain-Driven Design (DDD)** and secure **Firebase Authentication**.

GoalCrew empowers small communities (Pods) to track goals, share daily check-ins (reflections), maintain consistent streaks, and engage through social mechanics.

🔗 **Live Web Client**: [goal-crew-frontend.vercel.app](https://goal-crew-frontend.vercel.app/)

---

## 🛠️ Tech Stack & Key Choices

*   **FastAPI**: Selected for high-performance async capabilities, automatic OpenAPI documentation, and robust dependency injection.
*   **PostgreSQL & SQLAlchemy (Async)**: Utilizes fully asynchronous database engines and sessions (`AsyncSession`) to ensure maximum I/O throughput.
*   **Alembic**: Migration framework managing database schema evolution safely.
*   **Firebase Admin SDK**: Performs token verification and manages secure Custom Token generation for decoupled client authentication.
*   **Matplotlib & ReportLab**: Handles server-side chart rendering and builds downloadable PDF summaries of pod stats on the fly.
*   **Pydantic v2**: Handles high-speed data validation and serialization.
*   **Google GenAI SDK (Gemini Flash & text-embedding-004)**: Powers the hybrid AI accountability partner, handling intent routing, text-to-SQL generation, vector embeddings, and RAG synthesis.
*   **NumPy**: Executes SIMD-accelerated in-memory cosine similarity and vector dot-product computations for qualitative reflection retrieval.
*   **Celery & Redis (Optional)**: Ready for background queue management and event scheduling.


---

## 🏗️ Project Architecture

The backend follows a **Modular Monolith** style. Each domain/feature is decoupled into isolated modules under `app/modules/`. This makes it highly scalable and easier for teams to divide work.

```
GoalCrew_backend/
│
├── app/
│   ├── core/                  # Global handlers, error patterns
│   ├── db/                    # Session management and SQLAlchemy base models
│   ├── firebase/              # Auth middleware, Admin SDK initialization
│   ├── modules/               # Domain-specific modules (DDD)
│   │   ├── users/             # Registration, login, profile management
│   │   ├── pods/              # Pod creation, membership, invite codes
│   │   ├── goals/             # Goal tracking, Streaks management
│   │   ├── reflections/       # Daily check-ins, comments, and reactions
│   │   ├── reports/           # PDF generation services
│   │   ├── chatbot/           # AI Accountability partner integration
│   │   └── notifications/     # Event handlers and notifications dispatching
│   │
│   ├── utils/                 # Twilio SMS helper, email utils, AI helpers
│   ├── config.py              # Strict environment configuration (Pydantic Settings)
│   └── main.py                # FastAPI app lifecycle hooks & route registration
│
├── migrations/                # Alembic database migrations
├── tests/                     # Integration and unit test suite
├── requirements.txt           # Python dependencies
└── alembic.ini                # Alembic configuration
```

---

## 🚀 Outstanding Features

1.  **Strict Security & Decoupled Authentication**: The backend acts as a secure authenticator. It validates local credentials, issues a Firebase Custom Token, and leaves the client SDK to safely exchange it for a session ID token.
2.  **Domain Event Dispatcher**: Includes an async in-memory event dispatcher (`app/modules/events/`) that decoupling cross-cutting concerns. For example, creating a pod immediately triggers a `POD_CREATED` domain event, which notifications handlers pick up and act on independently.
3.  **On-Demand Report Engine**: An isolated `reports` service that aggregates pod member check-ins, charts performance using `matplotlib` in-memory, embeds the chart inside a dynamically styled `reportlab` PDF template, and streams the document as an attachment directly back to the client.
4.  **Streaks Reconciliation Engine**: Built-in cron-ready services (`GoalStreakReconciliationService`) that reconcile streaks daily and weekly, accounting for timezones and active goal schedules.
5.  **AI Accountability Partner & Hybrid RAG Engine**:
    *   **Intent-Based Routing**: Dynamically classifies natural-language queries into `ANALYTICS` (database stats) vs. `QUALITATIVE` (semantic check-ins) vs. `UNRELATED` using Google Gemini.
    *   **Semantic Vector Search (RAG)**: Automatically generates and stores 768-dimensional embeddings (`text-embedding-004`) for daily check-in reflections, executing pod-scoped in-memory cosine similarity searches with NumPy to ground AI responses with date and author citations.
    *   **Text-to-SQL Analytics**: Converts user questions about streaks, activity counts, and leaderboards into safe, CTE-scoped read-only PostgreSQL queries.
    *   **Database-Backed Rate Limiting**: Enforces persistent per-user quotas (1 call/min, 10 calls/24h) via `chatbot_query_logs` to protect Gemini API limits.

---

## ⚙️ Getting Started

### Prerequisites
*   Python 3.11+
*   PostgreSQL Database
*   Firebase Project (with service account credentials json)

### Installation

1.  **Clone the Repository** and navigate to the backend folder.
2.  **Create a Virtual Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment**:
    Copy `.env.example` to `.env` and fill out all keys:
    ```env
    DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/goalcrew_db
    FIREBASE_PROJECT_ID=your-project-id
    FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json
    SECRET_KEY=your-jwt-signing-secret
    # Email and SMS services config
    ```
5.  **Run Migrations**:
    ```bash
    alembic upgrade head
    ```
6.  **Start Dev Server**:
    ```bash
    uvicorn app.main:app --reload --port 8002
    ```
    Access the interactive API docs at `http://localhost:8002/docs`.
