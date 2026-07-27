from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from database import get_db
from models import User, ProjectMember, Project, Organization, OrganizationMember
import schemas
from utils.auth import get_current_user, require_org_admin, require_platform_admin
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

@router.get("/", response_model=List[schemas.OrganizationWithProjectsResponse])
async def get_all_organizations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.global_role == "platform_admin":
        result = await db.execute(select(Organization).options(selectinload(Organization.projects)))
        return result.scalars().all()
    else:
        # Get organizations the user belongs to
        result = await db.execute(
            select(Organization)
            .join(OrganizationMember)
            .where(OrganizationMember.user_id == current_user.id)
            .options(selectinload(Organization.projects))
        )
        return result.scalars().all()

class MemberResponse(BaseModel):
    id: str
    email: str
    full_name: str
    global_role: str
    org_role: str = "user" # from organization_members

    class Config:
        from_attributes = True

@router.get("/members", response_model=List[MemberResponse])
async def get_org_members(org_id: str = None, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    target_org_id = org_id
    if current_user.global_role == "org_admin" and not target_org_id:
        # Fallback to a user's org if not specified
        org_mem_result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id, OrganizationMember.role == "org_admin"))
        first_org = org_mem_result.scalars().first()
        if first_org:
            target_org_id = first_org.organization_id

    if not target_org_id:
        raise HTTPException(status_code=400, detail="Organization ID required")

    result = await db.execute(
        select(User, OrganizationMember.role.label("org_role"))
        .join(OrganizationMember)
        .where(OrganizationMember.organization_id == target_org_id)
    )
    
    users = []
    for user, org_role in result:
        users.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "global_role": user.global_role,
            "org_role": org_role
        })
    return users

class UpdateOrgRole(BaseModel):
    role: str

@router.put("/members/{user_id}/role")
async def update_org_member_role(user_id: str, org_id: str, data: UpdateOrgRole, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    if data.role not in ["user", "org_admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == org_id))
    org_member = result.scalars().first()
    
    if not org_member:
        raise HTTPException(status_code=404, detail="User not found in organization")
        
    # Check permissions
    if current_user.global_role != "platform_admin":
        checker = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id, OrganizationMember.organization_id == org_id, OrganizationMember.role == "org_admin"))
        if not checker.scalars().first():
            raise HTTPException(status_code=403, detail="Cannot modify user outside your organization")
        
    org_member.role = data.role
    await db.commit()
    return {"message": "Role updated successfully"}

@router.delete("/members/{user_id}")
async def remove_org_member(user_id: str, org_id: str, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == org_id))
    org_member = result.scalars().first()
    
    if not org_member:
        raise HTTPException(status_code=404, detail="User not found in organization")
        
    if current_user.global_role != "platform_admin":
        checker = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id, OrganizationMember.organization_id == org_id, OrganizationMember.role == "org_admin"))
        if not checker.scalars().first():
            raise HTTPException(status_code=403, detail="Cannot modify user outside your organization")
        
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
        
    await db.delete(org_member)
    # Delete project memberships for this user in this org
    projects_result = await db.execute(select(Project).where(Project.organization_id == org_id))
    project_ids = [p.id for p in projects_result.scalars().all()]
    if project_ids:
        await db.execute(
            ProjectMember.__table__.delete().where(
                ProjectMember.user_id == user_id,
                ProjectMember.project_id.in_(project_ids)
            )
        )
    await db.commit()
    return {"message": "User removed from organization"}

@router.get("/active_users", response_model=List[schemas.UserResponse])
async def get_active_users(current_user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_active == "true"))
    return result.scalars().all()

class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "user"

@router.post("/{org_id}/add_member")
async def add_member_to_org(org_id: str, data: AddMemberRequest, current_user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    # Check if already a member
    result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == data.user_id, OrganizationMember.organization_id == org_id))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="User is already in this organization")
    
    # Check if user exists
    user_res = await db.execute(select(User).where(User.id == data.user_id, User.is_active == "true"))
    if not user_res.scalars().first():
        raise HTTPException(status_code=404, detail="Active user not found")

    org_member = OrganizationMember(
        organization_id=org_id,
        user_id=data.user_id,
        role=data.role
    )
    db.add(org_member)
    await db.commit()
    return {"message": "User added to organization"}

@router.get("/{org_id}/users", response_model=List[schemas.UserResponse])
async def get_specific_org_users(org_id: str, current_user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .join(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
    )
    return result.scalars().all()
