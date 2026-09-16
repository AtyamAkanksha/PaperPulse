from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    materials = relationship("Material", back_populates="owner", cascade="all, delete-orphan")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="uploaded", nullable=False)  # e.g., "uploaded", "processing", "completed", "failed"
    extracted_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    quiz_json = Column(Text, nullable=True)

    owner = relationship("User", back_populates="materials")
