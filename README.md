# DevTalk - MVP Prototype

Community discussion platform. Assignment 4, Software Development Case Study.
Built with FastAPI + SQLAlchemy + PostgreSQL as specified in Assignment 1.

## What this prototype tests

The MVP hypothesis: registered users will return to a minimal forum without push reminders
because they value persistent, searchable discussions that chat apps cannot provide.

Core features implemented:
- Guest browsing - all posts visible without login
- User registration and login (JWT in httpOnly cookie, bcrypt rounds=12, 24h expiry)
- Post creation with title, body, and tags (validation matches A1 spec)
- Two-level nested comments with parent_id FK and depth check
- Upvote / downvote on posts and comments, no self-voting
- Keyword search across post titles and bodies (ILIKE)
- Tag filtering
- Auto-generated OpenAPI docs at /docs (NFR06)
- Indexes on posts.created_at, comments.post_id, votes.user_id (NFR01)

## Requirements

- Python 3.10+
- PostgreSQL 14+ (must be running before starting the app)

## Setup

### Step 1 - Create the PostgreSQL database

Open psql and run:

    CREATE USER devtalk_user WITH PASSWORD 'devtalk_pass';
    CREATE DATABASE devtalk OWNER devtalk_user;

### Step 2 - Install Python dependencies

    pip install -r requirements.txt

### Step 3 - Configure the connection (optional)

By default the app connects to:
    postgresql://devtalk_user:devtalk_pass@localhost:5432/devtalk

If your setup is different, set the environment variable before running:

    export DEVTALK_DATABASE_URL=postgresql://youruser:yourpass@localhost:5432/yourdb

On Windows (Command Prompt):
    set DEVTALK_DATABASE_URL=postgresql://youruser:yourpass@localhost:5432/yourdb

### Step 4 - Run the app

    uvicorn app.main:app --reload

Open http://localhost:8000 in your browser.
OpenAPI schema is at http://localhost:8000/docs

Tables are created automatically on first run. Five default tags are seeded:
general, questions, announcements, feedback, offtopic.

## Notes

- Passwords use bcrypt, work factor 12, as per NFR03 in Assignment 1.
- JWT tokens expire after 24 hours, as per NFR03.
- The SQLAlchemy ORM layer means switching back to SQLite for local testing
  is a one-line change in app/database.py (replace the DATABASE_URL).
- No email, no notifications, no mobile layout - all explicitly out of scope for the MVP.
