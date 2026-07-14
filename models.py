import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = 'organizations'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="organization")
    projects = relationship("Project", back_populates="organization")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=True) # Platform admin might not have an org, or could have a default one. Nullable allows platform admin without org.
    global_role = Column(String, default="user") # 'platform_admin', 'org_admin', 'user'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="users")
    project_memberships = relationship("ProjectMember", back_populates="user")

class Project(Base):
    __tablename__ = 'projects'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey('organizations.id'))
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="projects")
    connections = relationship("Connection", back_populates="project")
    business_schemas = relationship("BusinessSchema", back_populates="project")
    members = relationship("ProjectMember", back_populates="project")

class ProjectMember(Base):
    __tablename__ = 'project_members'

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey('projects.id'))
    user_id = Column(String, ForeignKey('users.id'))
    role = Column(String, default="viewer") # 'editor', 'viewer'
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="project_memberships")

class Invitation(Base):
    __tablename__ = 'invitations'

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey('organizations.id'))
    invited_by_id = Column(String, ForeignKey('users.id'))
    token = Column(String, unique=True, nullable=False)
    status = Column(String, default="pending") # 'pending', 'accepted'
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization")
    invited_by = relationship("User")

class Connection(Base):
    __tablename__ = 'connections'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey('projects.id'))
    name = Column(String, nullable=False)
    db_type = Column(String, nullable=False) # postgres, mysql, sqlite, mongodb
    connection_string_encrypted = Column(String)
    connection_details_encrypted = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="connections")

class BusinessSchema(Base):
    __tablename__ = 'business_schemas'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey('projects.id'))
    connection_id = Column(String, ForeignKey('connections.id'), nullable=True)
    name = Column(String, nullable=False)
    description = Column(String)
    fields = Column(JSON) # Array of logical fields
    physical_target_name = Column(String) # Table or collection name
    field_mappings = Column(JSON) # Map logical to physical
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="business_schemas")
    validation_runs = relationship("ValidationRun", back_populates="schema")

class ValidationRun(Base):
    __tablename__ = 'validation_runs'

    id = Column(String, primary_key=True, default=generate_uuid)
    schema_id = Column(String, ForeignKey('business_schemas.id'))
    compliance_score = Column(String) # Float stored as string or float depending on db, string for simplicity or Float
    total_records = Column(String)
    compliant_records = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    schema = relationship("BusinessSchema", back_populates="validation_runs")
