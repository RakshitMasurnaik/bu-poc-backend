from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel
from database import get_db
from models import User, Project, ProjectMember
import schemas
from utils.auth import get_current_user, require_org_admin

async def verify_project_admin(project_id: str, current_user: User, db: AsyncSession):
    if current_user.global_role == "platform_admin":
        return
        
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.global_role == "org_admin":
        if await is_user_in_org(current_user.id, project.organization_id, db, require_admin=True):
            return
            
    member_result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == current_user.id))
    membership = member_result.scalars().first()
    if not membership or membership.role != "project_admin":
        raise HTTPException(status_code=403, detail="Project admin access required")

router = APIRouter(prefix="/api/projects", tags=["projects"])

class ProjectMemberAssign(BaseModel):
    user_id: str
    role: str # 'project_admin', 'project_member'

@router.post("/", response_model=schemas.ProjectResponse)
async def create_project(project_data: schemas.ProjectCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_org_admin)):
    # Verify current_user is org admin for the requested org_id
    if current_user.global_role != "platform_admin":
        from models import OrganizationMember
        org_mem_result = await db.execute(select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == project_data.org_id,
            OrganizationMember.role == "org_admin"
        ))
        if not org_mem_result.scalars().first():
            raise HTTPException(status_code=403, detail="Not authorized to create project in this organization")

    new_project = Project(
        organization_id=project_data.org_id,
        name=project_data.name
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)

    # Automatically add the creator as a project admin
    new_member = ProjectMember(
        project_id=new_project.id,
        user_id=current_user.id,
        role="project_admin"
    )
    db.add(new_member)
    await db.commit()

    return new_project

@router.get("/", response_model=List[schemas.ProjectResponse])
async def list_projects(org_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Standard users only see projects they are members of
    if current_user.global_role == "platform_admin":
        result = await db.execute(select(Project).where(Project.organization_id == org_id))
    elif current_user.global_role == "org_admin":
        from models import OrganizationMember
        org_mem_result = await db.execute(select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == org_id,
            OrganizationMember.role == "org_admin"
        ))
        if org_mem_result.scalars().first():
            result = await db.execute(select(Project).where(Project.organization_id == org_id))
        else:
            result = await db.execute(
                select(Project).join(ProjectMember).where(
                    Project.organization_id == org_id,
                    ProjectMember.user_id == current_user.id
                )
            )
    else:
        result = await db.execute(
            select(Project).join(ProjectMember).where(
                Project.organization_id == org_id,
                ProjectMember.user_id == current_user.id
            )
        )
    return result.scalars().all()

async def is_user_in_org(user_id: str, org_id: str, db: AsyncSession, require_admin: bool = False):
    from models import OrganizationMember
    query = select(OrganizationMember).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id == org_id
    )
    if require_admin:
        query = query.where(OrganizationMember.role == "org_admin")
    
    result = await db.execute(query)
    return result.scalars().first() is not None

@router.post("/{project_id}/members")
async def assign_project_member(project_id: str, data: ProjectMemberAssign, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_project_admin(project_id, current_user, db)
    # verify project
    project_query = select(Project).where(Project.id == project_id)
    
    result = await db.execute(project_query)
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.global_role != "platform_admin":
        if not await is_user_in_org(current_user.id, project.organization_id, db):
            raise HTTPException(status_code=403, detail="Not authorized for this organization")

    # verify user to assign
    if not await is_user_in_org(data.user_id, project.organization_id, db):
        raise HTTPException(status_code=404, detail="User not found in this organization")
    
    # check if already member, if so update role, else create
    member_result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == data.user_id))
    member = member_result.scalars().first()

    if member:
        member.role = data.role
    else:
        member = ProjectMember(
            project_id=project_id,
            user_id=data.user_id,
            role=data.role
        )
        db.add(member)

    await db.commit()
    return {"message": "Project member assigned successfully"}

@router.get("/{project_id}", response_model=schemas.ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_query = select(Project).where(Project.id == project_id)
    
    project = (await db.execute(project_query)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.global_role != "platform_admin":
        # If standard user or org_admin, verify access
        if current_user.global_role == "org_admin" and await is_user_in_org(current_user.id, project.organization_id, db, require_admin=True):
            pass # Authorized as org admin
        else:
            member_result = await db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == current_user.id
                )
            )
            if not member_result.scalars().first():
                raise HTTPException(status_code=403, detail="Access denied to this project")

    return project

@router.put("/{project_id}/members/{user_id}")
async def update_project_member_role(project_id: str, user_id: str, data: schemas.ProjectMemberUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_project_admin(project_id, current_user, db)
    # verify project
    project_query = select(Project).where(Project.id == project_id)
    
    project = (await db.execute(project_query)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.global_role != "platform_admin":
        if not await is_user_in_org(current_user.id, project.organization_id, db):
            raise HTTPException(status_code=403, detail="Not authorized for this organization")

    target_user_result = await db.execute(select(User).where(User.id == user_id))
    target_user = target_user_result.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    member_result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id))
    member = member_result.scalars().first()

    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")

    if current_user.id == user_id:
        raise HTTPException(status_code=403, detail="Users cannot modify their own roles")

    if current_user.global_role not in ["platform_admin", "org_admin"]:
        if target_user.global_role in ["platform_admin", "org_admin"]:
            raise HTTPException(status_code=403, detail="Project admins cannot modify roles of organization admins")
        if member.role == "project_admin" and target_user.id != current_user.id:
            raise HTTPException(status_code=403, detail="Project admins cannot modify roles of other project admins")

    member.role = data.role
    await db.commit()
    return {"message": "Project member role updated successfully"}

@router.delete("/{project_id}/members/{user_id}")
async def remove_project_member(project_id: str, user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_project_admin(project_id, current_user, db)
    # verify project
    project_query = select(Project).where(Project.id == project_id)
    
    project = (await db.execute(project_query)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.global_role != "platform_admin":
        if not await is_user_in_org(current_user.id, project.organization_id, db):
            raise HTTPException(status_code=403, detail="Not authorized for this organization")

    target_user_result = await db.execute(select(User).where(User.id == user_id))
    target_user = target_user_result.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    member_result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id))
    member = member_result.scalars().first()

    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")

    if current_user.global_role not in ["platform_admin", "org_admin"]:
        if target_user.global_role in ["platform_admin", "org_admin"]:
            raise HTTPException(status_code=403, detail="Project admins cannot remove organization admins")
        if member.role == "project_admin" and target_user.id != current_user.id:
            raise HTTPException(status_code=403, detail="Project admins cannot remove other project admins")

    await db.delete(member)
    await db.commit()
    return {"message": "Project member removed successfully"}

@router.get("/{project_id}/members")
async def list_project_members(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_query = select(Project).where(Project.id == project_id)
    
    project = (await db.execute(project_query)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Standard user must be a member to list members (or org admin / platform admin)
    if current_user.global_role != "platform_admin":
        if current_user.global_role == "org_admin" and await is_user_in_org(current_user.id, project.organization_id, db, require_admin=True):
            pass # authorized
        else:
            member_result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == current_user.id))
            if not member_result.scalars().first():
                raise HTTPException(status_code=403, detail="Access denied to this project")

    result = await db.execute(
        select(User, ProjectMember)
        .join(ProjectMember, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
    )
    members = []
    for u, pm in result.all():
        members.append({
            "id": pm.id,
            "project_id": pm.project_id,
            "user_id": u.id,
            "role": pm.role,
            "created_at": pm.created_at,
            "user": {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "global_role": u.global_role,
                "created_at": u.created_at
            }
        })
    return members
