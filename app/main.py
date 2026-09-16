from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# Load environment variables from .env
load_dotenv()

from app.database import engine, Base, get_db
from app import models, schemas
from app.auth import (
    get_current_user,
    get_password_hash,
    authenticate_user,
    create_access_token,
)
from app.extractor import extract_text_from_pdf
from app.llm import generate_summary, generate_quiz

# Initialize database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PaperPulse API",
    description="A modular API for document processing, AI summarization, and quiz generation.",
    version="1.0.0",
)


@app.get("/", tags=["Health"])
def root():
    """Root health-check endpoint."""
    return {"message": "Welcome to PaperPulse API", "docs_url": "/docs"}


# --- Authentication & User Endpoints ---
@app.post(
    "/users",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
)
def register_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user, securely hash their password with passlib,
    and save them to the database while preventing duplicate emails.
    """
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered.",
        )

    hashed_pw = get_password_hash(user_in.password)
    user = models.User(email=user_in.email, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post(
    "/auth/login",
    response_model=schemas.Token,
    tags=["Auth"],
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate user credentials via OAuth2PasswordRequestForm
    and return a signed JWT access token.
    """
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get(
    "/users/me",
    response_model=schemas.UserResponse,
    tags=["Users"],
)
def get_me(current_user: models.User = Depends(get_current_user)):
    """Fetch current authenticated user profile protected by JWT."""
    return current_user


# --- Material Pipeline Endpoints ---
@app.post(
    "/materials/upload",
    response_model=schemas.MaterialUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Materials"],
)
async def upload_material(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Protected endpoint: Accepts a multipart PDF file, extracts text using PyMuPDF (fitz)
    with PyTesseract OCR fallback for scanned pages, saves the material with status 'uploaded',
    and returns the material ID and filename.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Validate file type / extension
    filename = file.filename or "uploaded_document.pdf"
    
    # Process text extraction (digital layer with OCR fallback for PDFs)
    try:
        if filename.lower().endswith(".pdf") or file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(file_bytes)
        else:
            # Fallback for plain text files
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process document: {str(exc)}",
        )

    material = models.Material(
        owner_id=current_user.id,
        filename=filename,
        status="uploaded",
        extracted_text=extracted_text,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    preview = (extracted_text[:200] + "...") if extracted_text and len(extracted_text) > 200 else extracted_text

    return schemas.MaterialUploadResponse(
        id=material.id,
        filename=material.filename,
        status=material.status,
        extracted_text_preview=preview,
    )


@app.get(
    "/materials",
    response_model=List[schemas.MaterialResponse],
    tags=["Materials"],
)
def list_materials(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all materials owned by the authenticated user."""
    return db.query(models.Material).filter(models.Material.owner_id == current_user.id).all()


@app.get(
    "/materials/{id}",
    response_model=schemas.MaterialResponse,
    tags=["Materials"],
)
def get_material(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve material details by ID. Protected by JWT."""
    material = (
        db.query(models.Material)
        .filter(models.Material.id == id, models.Material.owner_id == current_user.id)
        .first()
    )
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found.",
        )
    return material


@app.post(
    "/materials/{id}/summary",
    response_model=schemas.SummaryResponse,
    tags=["Materials"],
)
async def generate_material_summary(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Protected endpoint: Fetches material by ID, updates status to 'processing',
    sends extracted_text to the LLM to generate a structured summary, saves the
    summary to the database, updates status to 'completed', and returns the summary.
    """
    material = (
        db.query(models.Material)
        .filter(models.Material.id == id, models.Material.owner_id == current_user.id)
        .first()
    )
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found.",
        )

    # 1. Update status to 'processing'
    material.status = "processing"
    db.commit()
    db.refresh(material)

    # 2. Call LLM to generate summary
    summary_text = await generate_summary(
        text=material.extracted_text or "",
        filename=material.filename,
    )

    # 3. Save summary and update status to 'completed'
    material.summary = summary_text
    material.status = "completed"
    db.commit()
    db.refresh(material)

    return schemas.SummaryResponse(
        material_id=material.id,
        summary=material.summary,
        status=material.status,
    )


@app.post(
    "/materials/{id}/quiz",
    response_model=schemas.QuizResponse,
    tags=["Materials"],
)
async def generate_material_quiz(
    id: int,
    request: Optional[schemas.QuizGenerateRequest] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Protected endpoint: Fetches material by ID, updates status to 'processing',
    sends extracted_text to LLM with strict instructions to output a JSON array of MCQs,
    validates the output with Pydantic QuizSchema, saves JSON string to quiz_json,
    updates status to 'completed', and returns the generated quiz.
    """
    material = (
        db.query(models.Material)
        .filter(models.Material.id == id, models.Material.owner_id == current_user.id)
        .first()
    )
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found.",
        )

    # 1. Update status to 'processing'
    material.status = "processing"
    db.commit()
    db.refresh(material)

    num_q = request.num_questions if request and request.num_questions else 4

    # 2. Call LLM with Pydantic schema validation
    quiz_result = await generate_quiz(
        text=material.extracted_text or "",
        filename=material.filename,
        num_questions=num_q,
    )

    # 3. Store structured JSON string and update status to 'completed'
    material.quiz_json = quiz_result.model_dump_json()
    material.status = "completed"
    db.commit()
    db.refresh(material)

    return schemas.QuizResponse(
        material_id=material.id,
        quiz=quiz_result,
        status=material.status,
    )
