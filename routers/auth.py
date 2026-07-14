from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm
from database import get_db
from models import User, Organization, Invitation
import schemas
import secrets
from utils.auth import get_password_hash, verify_password, create_access_token, get_current_user, require_org_admin
from utils.email import send_invitation_email
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Create org
    new_org = Organization(name=user_data.organization_name)
    db.add(new_org)
    await db.flush() # flush to get org ID
    
    # Create user as org admin by default for self-registration
    hashed_pwd = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_pwd,
        full_name=user_data.full_name,
        organization_id=new_org.id,
        global_role="org_admin"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(invite_data: schemas.InviteRequest, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    # Check if email is already a user
    result = await db.execute(select(User).where(User.email == invite_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="User already exists")

    # Generate a secure token
    token = secrets.token_urlsafe(32)
    
    new_invitation = Invitation(
        email=invite_data.email,
        organization_id=current_user.organization_id,
        invited_by_id=current_user.id,
        token=token
    )
    db.add(new_invitation)
    await db.commit()

    # Send the email via Resend
    send_invitation_email(invite_data.email, token)
    
    return {"message": "Invitation sent successfully"}

@router.post("/activate", response_model=schemas.UserResponse)
async def activate_user(activate_data: schemas.ActivateRequest, db: AsyncSession = Depends(get_db)):
    # Validate token
    result = await db.execute(select(Invitation).where(Invitation.token == activate_data.token, Invitation.status == "pending"))
    invitation = result.scalars().first()
    
    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Create user
    hashed_pwd = get_password_hash(activate_data.password)
    new_user = User(
        email=invitation.email,
        hashed_password=hashed_pwd,
        full_name=activate_data.full_name,
        organization_id=invitation.organization_id,
        global_role="user" # Default to user
    )
    db.add(new_user)
    
    # Update invitation status
    invitation.status = "accepted"
    
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(hours=2)
    access_token = create_access_token(
        data={"sub": user.id, "org": user.organization_id, "role": user.global_role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
