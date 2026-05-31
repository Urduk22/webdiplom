from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models import User
from backend.service.auth_service import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/register")
async def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(400, "Username already exists")
    hashed = get_password_hash(password)
    user = User(username=username, hashed_password=hashed, role="user")
    db.add(user)
    db.commit()
    return {"message": "User created"}

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}