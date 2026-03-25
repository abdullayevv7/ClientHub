# ClientHub - Customer Relationship Management System

## Description

ClientHub is a production-grade, full-featured Customer Relationship Management (CRM) platform designed for modern sales teams. It provides end-to-end management of customer relationships, sales pipelines, contact management, deal tracking, task automation, email integration, reporting/analytics, and team collaboration -- all through an intuitive web interface backed by a robust API.

## Goal

To deliver a scalable, extensible CRM system that empowers sales organizations to:

- Centralize customer data and communication history
- Visualize and manage sales pipelines with drag-and-drop deal boards
- Automate repetitive tasks and follow-up reminders
- Generate actionable reports and revenue forecasts
- Enable seamless team collaboration with role-based access control

## Features

### Core Modules

- **Contact Management** -- Create, search, filter, tag, and annotate contacts and companies. Full-text search powered by Elasticsearch.
- **Deal Pipeline** -- Kanban-style pipeline boards with customizable stages, weighted probability, and automatic activity logging.
- **Task Management** -- Assign, prioritize, and track tasks with due dates, comments, and Celery-powered reminders.
- **Email Integration** -- Templated email campaigns, send/receive logging, and campaign analytics.
- **Reports & Analytics** -- Revenue dashboards, pipeline funnels, conversion rates, sales leaderboards, and exportable reports.
- **Activity Feed** -- Chronological log of every action across the system for full audit trailing.
- **Team Collaboration** -- Team-based data scoping, shared pipelines, and internal notes.

### Technical Features

- JWT authentication with token refresh
- Role-based access control (RBAC)
- Real-time search with Elasticsearch
- Background job processing with Celery + Redis
- Pagination, filtering, and ordering on all list endpoints
- Docker-based development and deployment
- Nginx reverse proxy with static file serving
- Split Django settings (development / production)

## Architecture

```
                    +------------+
                    |   Nginx    |
                    | (Reverse   |
                    |  Proxy)    |
                    +-----+------+
                          |
              +-----------+-----------+
              |                       |
      +-------v-------+     +--------v--------+
      | React Frontend|     | Django REST API  |
      | (Port 3000)   |     | (Port 8000)     |
      +---------------+     +--------+--------+
                                     |
                    +----------------+----------------+
                    |                |                 |
            +-------v---+   +-------v------+   +------v-------+
            | PostgreSQL |   |    Redis     |   | Elasticsearch|
            | (Port 5432)|   | (Port 6379)  |   | (Port 9200)  |
            +------------+   +-------+------+   +--------------+
                                     |
                              +------v------+
                              |   Celery    |
                              |   Worker    |
                              +------+------+
                                     |
                              +------v------+
                              | Celery Beat |
                              | (Scheduler) |
                              +-------------+
```

## Tech Stack

| Layer         | Technology                          |
|---------------|-------------------------------------|
| Backend       | Python 3.11, Django 4.2, DRF 3.14   |
| Frontend      | React 18, Redux Toolkit, Recharts   |
| Database      | PostgreSQL 15                       |
| Cache/Broker  | Redis 7                             |
| Task Queue    | Celery 5.3                          |
| Search        | Elasticsearch 8                     |
| Web Server    | Nginx 1.25                          |
| Containers    | Docker, Docker Compose              |

## Folder Structure

```
ClientHub/
|-- README.md
|-- docker-compose.yml
|-- .env.example
|-- .gitignore
|-- Makefile
|-- nginx/
|   +-- nginx.conf
|-- backend/
|   |-- manage.py
|   |-- requirements.txt
|   |-- config/
|   |   |-- __init__.py
|   |   |-- settings/
|   |   |   |-- __init__.py
|   |   |   |-- base.py
|   |   |   |-- development.py
|   |   |   +-- production.py
|   |   |-- urls.py
|   |   |-- wsgi.py
|   |   +-- celery.py
|   |-- apps/
|   |   |-- __init__.py
|   |   |-- accounts/    (User, Team, Role, auth)
|   |   |-- contacts/    (Contact, Company, tags, notes)
|   |   |-- deals/       (Deal, Pipeline, DealStage, activities)
|   |   |-- tasks/       (Task, comments, reminders)
|   |   |-- emails/      (Templates, campaigns, logs)
|   |   |-- reports/     (Dashboards, analytics)
|   |   +-- activities/  (Activity log / audit trail)
|   +-- utils/
|       |-- __init__.py
|       |-- pagination.py
|       |-- permissions.py
|       +-- exceptions.py
+-- frontend/
    |-- package.json
    |-- public/
    |   +-- index.html
    +-- src/
        |-- index.js
        |-- App.jsx
        |-- api/
        |-- components/
        |-- pages/
        |-- store/
        |-- hooks/
        +-- styles/
```

## Setup

### Prerequisites

- Docker and Docker Compose installed
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/clienthub.git
cd clienthub

# Copy environment variables
cp .env.example .env

# Build and start all services
make build
make up

# Run database migrations
make migrate

# Create a superuser
make superuser

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/api/
# Admin panel: http://localhost:8000/admin/
```

### Development (without Docker)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend
cd frontend
npm install
npm start
```

### Makefile Commands

| Command            | Description                              |
|--------------------|------------------------------------------|
| `make build`       | Build all Docker images                  |
| `make up`          | Start all services                       |
| `make down`        | Stop all services                        |
| `make migrate`     | Run Django migrations                    |
| `make superuser`   | Create a Django superuser                |
| `make test`        | Run backend tests                        |
| `make lint`        | Lint backend code                        |
| `make logs`        | Tail container logs                      |
| `make shell`       | Open Django shell                        |
| `make flush`       | Flush the database                       |

## API Documentation

### Authentication

All API endpoints (except login/register) require a valid JWT token.

```
POST   /api/auth/login/          - Obtain JWT token pair
POST   /api/auth/register/       - Register a new user
POST   /api/auth/token/refresh/  - Refresh access token
POST   /api/auth/logout/         - Blacklist refresh token
GET    /api/auth/me/             - Current user profile
```

### Contacts

```
GET    /api/contacts/                  - List contacts (filterable, searchable)
POST   /api/contacts/                  - Create a contact
GET    /api/contacts/{id}/             - Retrieve a contact
PUT    /api/contacts/{id}/             - Update a contact
DELETE /api/contacts/{id}/             - Delete a contact
GET    /api/contacts/{id}/notes/       - List contact notes
POST   /api/contacts/{id}/notes/       - Add a note to a contact
GET    /api/companies/                 - List companies
POST   /api/companies/                 - Create a company
GET    /api/companies/{id}/            - Retrieve a company
PUT    /api/companies/{id}/            - Update a company
DELETE /api/companies/{id}/            - Delete a company
```

### Deals

```
GET    /api/deals/                     - List deals (filterable)
POST   /api/deals/                     - Create a deal
GET    /api/deals/{id}/                - Retrieve a deal
PUT    /api/deals/{id}/                - Update a deal
PATCH  /api/deals/{id}/move/           - Move deal to a different stage
DELETE /api/deals/{id}/                - Delete a deal
GET    /api/pipelines/                 - List pipelines
POST   /api/pipelines/                 - Create a pipeline
GET    /api/pipelines/{id}/            - Retrieve pipeline with stages
GET    /api/pipelines/{id}/deals/      - List deals in a pipeline
```

### Tasks

```
GET    /api/tasks/                     - List tasks
POST   /api/tasks/                     - Create a task
GET    /api/tasks/{id}/                - Retrieve a task
PUT    /api/tasks/{id}/                - Update a task
PATCH  /api/tasks/{id}/complete/       - Mark task as complete
DELETE /api/tasks/{id}/                - Delete a task
POST   /api/tasks/{id}/comments/       - Add a comment
GET    /api/tasks/{id}/comments/       - List comments
```

### Emails

```
GET    /api/emails/templates/          - List email templates
POST   /api/emails/templates/          - Create a template
POST   /api/emails/send/               - Send an email
GET    /api/emails/campaigns/          - List campaigns
POST   /api/emails/campaigns/          - Create a campaign
POST   /api/emails/campaigns/{id}/send/ - Execute a campaign
GET    /api/emails/logs/               - Email send history
```

### Reports

```
GET    /api/reports/dashboard/         - Dashboard summary data
GET    /api/reports/revenue/           - Revenue analytics
GET    /api/reports/pipeline/          - Pipeline funnel data
GET    /api/reports/sales-performance/ - Sales rep leaderboard
GET    /api/reports/conversion/        - Conversion rate analytics
GET    /api/reports/export/            - Export report as CSV
```

### Activities

```
GET    /api/activities/                - Activity feed (filterable by entity)
```

## User Roles

| Role            | Permissions                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| **Admin**       | Full system access. Manage users, teams, pipelines, settings, and reports. |
| **Sales Manager** | Manage team deals, contacts, and tasks. View team reports. Manage pipeline stages. |
| **Sales Rep**   | Manage own deals, contacts, and tasks. View own performance reports.        |
| **Support Agent** | View contacts and deals (read-only on deals). Manage support tasks. Add contact notes. |

### Permission Matrix

| Resource        | Admin | Sales Manager | Sales Rep | Support Agent |
|-----------------|-------|---------------|-----------|---------------|
| Users           | CRUD  | Read          | Self only | Self only     |
| Teams           | CRUD  | Read own      | Read own  | Read own      |
| Contacts        | CRUD  | CRUD (team)   | CRUD (own)| Read + Notes  |
| Companies       | CRUD  | CRUD (team)   | CRUD (own)| Read          |
| Deals           | CRUD  | CRUD (team)   | CRUD (own)| Read          |
| Pipelines       | CRUD  | CRUD          | Read      | Read          |
| Tasks           | CRUD  | CRUD (team)   | CRUD (own)| CRUD (own)    |
| Email Templates | CRUD  | CRUD          | Read      | Read          |
| Email Campaigns | CRUD  | CRUD          | Send      | --            |
| Reports         | All   | Team          | Own       | --            |
| Settings        | CRUD  | Read          | --        | --            |

## Business Logic

### Deal Lifecycle

1. A deal is created and assigned to a pipeline stage (e.g., "Lead" -> "Qualified" -> "Proposal" -> "Negotiation" -> "Closed Won" / "Closed Lost").
2. Moving a deal between stages logs an activity and updates weighted revenue.
3. Closing a deal (won/lost) triggers email notifications and updates reports.
4. Each stage has a probability percentage used for revenue forecasting.

### Lead Scoring

- Contacts accumulate a score based on interactions (emails opened, meetings held, deals associated).
- Higher scores surface contacts in priority lists.

### Task Automation

- Overdue tasks trigger Celery-based email reminders.
- Recurring reminders are scheduled via Celery Beat.
- Task completion updates related deal activities.

### Email Campaigns

- Templates support variable interpolation (contact name, company, deal value).
- Campaigns track delivery, open, and click rates.
- Sending is offloaded to Celery workers for non-blocking execution.

### Reporting

- Revenue reports aggregate deal values by stage, owner, and time period.
- Pipeline funnels show conversion between stages.
- Sales performance ranks reps by closed deals, revenue, and activity count.

## Roadmap

- [x] Core contact and company management
- [x] Deal pipeline with Kanban board
- [x] Task management with reminders
- [x] Email template system
- [x] Role-based access control
- [x] Activity logging
- [x] Dashboard with analytics widgets
- [ ] WebSocket-based real-time notifications
- [ ] Calendar integration (Google Calendar, Outlook)
- [ ] VoIP integration for call logging
- [ ] Mobile-responsive progressive web app (PWA)
- [ ] AI-powered deal scoring and next-best-action suggestions
- [ ] Zapier / webhook integrations
- [ ] Multi-language (i18n) support
- [ ] Advanced data import/export (CSV, Excel, vCard)
- [ ] Custom fields and forms builder
- [ ] Two-factor authentication (2FA)

## License

This project is proprietary software. All rights reserved.
