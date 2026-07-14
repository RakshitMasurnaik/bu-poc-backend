import asyncio
from database import async_session
from sqlalchemy.future import select
from models import ProjectMember

async def update_roles():
    async with async_session() as db:
        result = await db.execute(select(ProjectMember))
        members = result.scalars().all()
        for m in members:
            if m.role == 'editor':
                m.role = 'project_admin'
            elif m.role == 'viewer':
                m.role = 'project_member'
        await db.commit()
        print("Updated project roles.")

asyncio.run(update_roles())
