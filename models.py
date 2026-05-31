from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import random
import string

def generate_public_id(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    surveys = relationship("Survey", back_populates="owner")

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    public_id = Column(String(10), unique=True, index=True, nullable=False, default=generate_public_id)
    owner = relationship("User", back_populates="surveys")
    questions = relationship("Question", back_populates="survey", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="survey", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    text = Column(String)
    question_type = Column(String)
    scale_min = Column(Integer, default=1)
    scale_max = Column(Integer, default=10)
    order = Column(Integer)
    survey = relationship("Survey", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    text = Column(String)
    question = relationship("Question", back_populates="options")

class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    respondent_id = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    survey = relationship("Survey", back_populates="responses")
    answers = relationship("Answer", back_populates="response", cascade="all, delete-orphan")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("responses.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    text_value = Column(Text, nullable=True)
    numeric_value = Column(Float, nullable=True)
    option_id = Column(Integer, ForeignKey("options.id"), nullable=True)
    multiple_option_ids = Column(Text, nullable=True)
    response = relationship("Response", back_populates="answers")
    question = relationship("Question")
    option = relationship("Option")