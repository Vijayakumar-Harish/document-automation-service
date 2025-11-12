# Document Automation Service

## 📌 Overview

This project implements a **document management and OCR automation backend** designed to demonstrate backend design, data modeling, and system-level thinking.
It is built using **FastAPI**, **MongoDB**, and integrates **OpenAI OCR (GPT-4o-mini Vision)** for intelligent document text extraction and classification.

---

## 🏗️ Tech Stack

| Component             | Technology                               |
| --------------------- | ---------------------------------------- |
| **Backend Framework** | FastAPI (Python 3.11)                    |
| **Database**          | MongoDB (Async with Motor)               |
| **Storage**           | GridFS for large files                   |
| **Authentication**    | JWT-based mock auth                      |
| **RBAC**              | Admin / Support / Moderator / User roles |
| **OCR**               | OpenAI Vision (GPT-4o-mini)              |
| **Containerization**  | Docker + docker-compose                  |
| **Utilities**         | OpenAI     |

---

## ⚙️ Setup & Run

### 🧩 Prerequisites

* Docker & Docker Compose installed
* An OpenAI API Key (`OPENAI_API_KEY`)

### 🪄 Environment File (`.env`)

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
MONGO_URL=mongodb://mongo:27017/assignment
```

### 🧰 Build & Start

```bash
docker-compose up --build
```

The API will start at:

```
http://localhost:8000
```

---

## 🚀 Implemented Features

### ✅ 1. Document Management

* Upload documents with **primary & secondary tags**
* Stored in **MongoDB GridFS** (supports large files)
* Audit logging for every upload
* Enforces **primary tag uniqueness per document**

**Endpoints:**

```http
POST /v1/docs
GET /v1/docs/{id}
```

---

### ✅ 2. Folder & Tag System

* Each **primary tag acts as a folder**.
* Can list all folders with document counts.
* Can retrieve documents within a specific folder.

**Endpoints:**

```http
GET /v1/folders
GET /v1/folders/{tag}/docs
```

---

### ✅ 3. Scoped Actions (Agent Simulation)

* Supports actions like:

  * `make_document`
  * `make_csv`
* Validates query scope (`folder` or `file`, not both)
* Deducts **credits (5 per request)** and tracks monthly usage.
* Stores generated results as new documents.

**Endpoints:**

```http
POST /v1/actions/run
GET /v1/actions/usage/month
```

---

### ✅ 4. OCR Webhook (Classifier)

* Accepts OCR ingestion payloads
* Classifies documents as `official` or `ad`
* Extracts unsubscribe email/URL for ads
* Enforces **rate-limit: 3 tasks per sender per user per day**
* Creates follow-up `Task` entries for ads
* Logs all OCR events in **audit log**

**Endpoints:**

```http
POST /v1/webhooks/ocr
```

---

### ✅ 5. OCR Scanner Integration (GPT-4o Vision)

* Added `/v1/docs/ocr-scan` endpoint.
* Allows direct upload of **image**.
* Auto-classifies text as `official` or `ad`.
* Saves extracted text to MongoDB.
* Creates audit log for every OCR scan.

**Endpoints:**

```http
POST /v1/docs/ocr-scan
```

---

### ✅ 6. RBAC (Role-Based Access Control)

Roles:

* **Admin** → Full access
* **User** → CRUD on own documents, run actions
* **Support / Moderator** → Read-only access only

**Enforced via:**
Custom dependency `require_role()` used in every route.

---

### ✅ 7. Auditing & Metrics

Every important action is logged into an `audit_logs` collection:

* Document uploads
* Tag operations
* Scoped actions
* OCR & webhook ingestion
* Task creation

**Metrics Endpoint**

```json
GET /v1/metrics
{
  "docs_total": 123,
  "folders_total": 7,
  "actions_month": 42,
  "tasks_today": 5
}
```

---

## 🧪 Testing

Planned and partially covered tests:

* Folder vs. file scope validation
* Primary tag uniqueness constraint
* Role-based access control enforcement
* Webhook rate-limiting
* Credit tracking accuracy

### Run:

```bash
pytest -v
```

---

## 📚 API Reference (Example curl calls)

### Upload a document

```bash
curl -X POST "http://localhost:8000/v1/docs?primaryTag=reports" \
  -H "Authorization: Bearer <user_jwt>" \
  -F "file=@sample.pdf"
```

### List folders

```bash
curl -H "Authorization: Bearer <user_jwt>" http://localhost:8000/v1/folders
```

### OCR Scan (PDF or Image)

```bash
curl -X POST "http://localhost:8000/v1/docs/ocr-scan" \
  -H "Authorization: Bearer <user_jwt>" \
  -F "file=@sample.pdf"
```

---

## ⚠️ Challenges Faced & Solutions

| Challenge                 | Description                                                      | Solution                                                            |
| ------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Async GridFS**          | GridFS requires synchronous DB object, but we use Motor (async). | Used `AsyncIOMotorGridFSBucket` instead of `GridFS`.                |
| **Role Enforcement**      | `support` role could modify data initially.                      | Tightened `require_role()` to check strict permissions.             |
| **Webhook Rate Limiting** | Counter updates in MongoDB didn’t rollback correctly.            | Fixed using atomic `find_one_and_update` and decrement rollback.    |
| **OCR Image Handling**    | OpenAI Vision rejected base64 string as URL.                     | Corrected JSON format to `{ "image_url": { "url": base64_data } }`. |
| **PDF OCR Support**       | OpenAI rejected PDFs (`invalid_image_format`).                   | Added PDF→Image conversion with `pdf2image` + `Pillow`.             |
| **Container Env Vars**    | OpenAI key not loaded in Docker.                                 | Added `.env` + `env_file` section in `docker-compose.yml`.          |
| **Testing Rate Limits**   | Curl repeated posts ignored limit check.                         | Ensured per-day per-sender key (`userId:source:date`).              |
| **GridFS Integration**    | Async write errors with `await fs.open_upload_stream()`.         | Replaced with async context manager `open_upload_stream`.           |

---

## 🕒 Timeline

| Day               | Task                                                                    |
| ----------------- | ----------------------------------------------------------------------- |
| **Day 1**         | Project setup, Docker, MongoDB schema, CRUD OPERATIONS and OPENAI Integration|


---

## 🧾 Author

**Harish V**
Backend Developer – MERN & Python Stack
ONE PROJECT AT A TIME! MADE WITH 💖

---
