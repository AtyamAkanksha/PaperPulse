# PaperPulse
> **A FastAPI mini-app that turns PDFs into smart summaries and quizzes using OCR and AI.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-fitz-brightgreen.svg)](https://pymupdf.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PaperPulse is a modular, production-ready FastAPI application that ingests PDF documents, extracts text using PyMuPDF with an automatic Tesseract OCR fallback for scanned pages, generates concise AI summaries, and creates strictly typed, multiple-choice quizzes validated with Pydantic.

---

## 🌟 Feature Breakdown

1. **Authentication & User Management**
   - User registration (`POST /users`) with email duplication checks.
   - Secure password hashing using `passlib` with `bcrypt`.
   - OAuth2 Password Bearer flow (`POST /auth/login`) returning signed JWT tokens (`python-jose`).
   - Reusable `get_current_user` FastAPI dependency protecting private endpoints.

2. **Document Processing with OCR Fallback**
   - Fast, in-memory PDF parsing using **PyMuPDF (`fitz`)**.
   - Automatic fallback to **PyTesseract OCR** if digital text layers are empty or sparse (< 50 characters, scanned documents).
   - Document lifecycle state tracking (`uploaded` ➔ `processing` ➔ `completed`).

3. **AI-Powered Summarization**
   - Multi-provider support for **Groq** (`llama-3.3-70b-versatile`) and **OpenAI** (`gpt-4o-mini`).
   - Generates structured, bulleted summaries highlighting core takeaways and key findings.
   - Intelligent local development fallback when API keys are not yet configured.

4. **Structured Quiz Generation & Pydantic Validation**
   - LLM prompt engineering strictly enforcing JSON output.
   - Validated against Pydantic models (`QuizSchema`, `QuizQuestion`) ensuring question text, 4 distinct options, correct answer, and explanations.
   - Serialized directly to SQLite (`quiz_json`) and served via typed API responses.

---

## 📁 Repository Structure

```text
PaperPulse/
├── app/
│   ├── __init__.py      # Package marker
│   ├── database.py      # SQLite connection, SessionLocal, and get_db dependency
│   ├── models.py        # SQLAlchemy User and Material models with status tracking
│   ├── schemas.py       # Pydantic validation schemas (User, Token, Material, Quiz)
│   ├── auth.py          # Password hashing, JWT creation, and get_current_user dependency
│   ├── extractor.py     # In-memory PDF text extraction with PyTesseract OCR fallback
│   ├── llm.py           # OpenAI / Groq client with markdown cleaning & Pydantic validation
│   └── main.py          # FastAPI application & route endpoints
├── colab_demo.py        # Standalone programmatic demo script for Colab / local testing
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── .gitignore           # Git ignore configuration
└── README.md            # Project documentation
```

---

## 🚀 Step-by-Step Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/paperpulse.git
cd paperpulse
```

### 2. Set Up a Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows (PowerShell / CMD):
.venv\Scripts\activate

# Activate on macOS / Linux:
source .venv/bin/activate
```

### 3. Install Requirements
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` template to `.env`:
```bash
# On Windows (PowerShell):
Copy-Item .env.example .env

# On macOS / Linux:
cp .env.example .env
```

Edit `.env` with your preferred settings and API keys:
```env
# Security & JWT Authentication
SECRET_KEY=your-super-secret-jwt-key
JWT_SECRET_KEY=your-super-secret-jwt-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM Providers (Configure at least one)
# 1. Groq (Recommended for speed)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# 2. OpenAI
OPENAI_API_KEY=sk-your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Optional: Path to Tesseract OCR executable on Windows
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## 💻 Terminal Run Commands

Start the development server with live reload:
```bash
uvicorn app.main:app --reload
```

Once running, explore the interactive documentation:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

> 📖 **Looking for a detailed walkthrough?** Check out the [Step-by-Step Execution Guide (RUN_GUIDE.md)](RUN_GUIDE.md) for full visual instructions on registering, authorizing, uploading PDFs, and generating summaries/quizzes in Swagger UI.

---

## 📋 Core Route List

| Method | Endpoint | Description | Auth Protected |
| :--- | :--- | :--- | :---: |
| `POST` | `/users` | Registers a new user account with duplicate email rejection & bcrypt hashing. | No |
| `POST` | `/auth/login` | Authenticates user via `OAuth2PasswordRequestForm` and returns a signed JWT token. | No |
| `POST` | `/materials/upload` | Accepts a multipart PDF file, extracts text via PyMuPDF/OCR, and stores it with status `"uploaded"`. | **Yes (JWT)** |
| `POST` | `/materials/{id}/summary` | Fetches material, sets status to `"processing"`, generates AI summary, and completes. | **Yes (JWT)** |
| `POST` | `/materials/{id}/quiz` | Generates structured MCQs from document text, validates against `QuizSchema`, and saves to DB. | **Yes (JWT)** |
| `GET` | `/users/me` | Retrieves the profile of the currently authenticated user. | **Yes (JWT)** |
| `GET` | `/materials` | Lists all materials owned by the authenticated user. | **Yes (JWT)** |
| `GET` | `/materials/{id}` | Retrieves details and current status of a specific material. | **Yes (JWT)** |

---

## 🧪 Google Colab & Automated Demo

A complete end-to-end demo script is included in [`colab_demo.py`](file:///d:/Own%20Projects/PaperPulse/colab_demo.py). It programmatically creates an in-memory PDF, registers a user, obtains a JWT token, uploads the PDF, generates a summary, and prints the validated quiz.

### Running Locally:
With your virtual environment active, simply execute:
```bash
python colab_demo.py
```

### Running in Google Colab:
In Google Colab, copy the cells from the [Google Colab Instructions](#google-colab-notebook-cells) or clone this repository in a cell and execute:
```python
!git clone https://github.com/your-username/paperpulse.git
%cd paperpulse
!pip install -r requirements.txt
!python colab_demo.py
```
