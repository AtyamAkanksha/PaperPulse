from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# --- Structured Quiz Schemas ---
class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: Optional[str] = None


class QuizSchema(BaseModel):
    title: Optional[str] = "Generated Quiz"
    questions: List[QuizQuestion]


class QuizGenerateRequest(BaseModel):
    num_questions: Optional[int] = 5


# --- Material Schemas ---
class MaterialBase(BaseModel):
    filename: str


class MaterialCreate(MaterialBase):
    extracted_text: Optional[str] = None


class MaterialResponse(MaterialBase):
    id: int
    owner_id: int
    status: str
    extracted_text: Optional[str] = None
    summary: Optional[str] = None
    quiz_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MaterialUploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    extracted_text_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SummaryResponse(BaseModel):
    material_id: int
    summary: str
    status: str


class QuizResponse(BaseModel):
    material_id: int
    quiz: QuizSchema
    status: str
