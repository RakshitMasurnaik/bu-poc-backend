from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base

from routers import auth, connections, schemas, projects, organizations
from models import User
from utils.auth import get_password_hash
from sqlalchemy.future import select
from database import async_session

app = FastAPI(
    title="Database Integration Platform API",
    description="SaaS Database Integration & Business Schema Induction Platform",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(connections.router)
app.include_router(schemas.router)
app.include_router(organizations.router)

@app.on_event("startup")
async def startup_db_client():
    async with engine.begin() as conn:
        # Create all tables (dev only)
        await conn.run_sync(Base.metadata.create_all)
        
    # Seed platform user
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == "platform@example.com"))
        platform_user = result.scalars().first()
        if not platform_user:
            print("Seeding Platform Admin user...")
            new_platform_user = User(
                email="platform@example.com",
                hashed_password=get_password_hash("Platform@123"),
                full_name="Platform Admin",
                global_role="platform_admin"
            )
            db.add(new_platform_user)
            await db.commit()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API is running"}
