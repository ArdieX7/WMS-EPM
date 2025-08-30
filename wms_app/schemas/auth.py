from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    permissions: List[str] = []

class Role(RoleBase):
    id: int
    permissions: List[str] = []  # Lista dei nomi dei permessi
    
    class Config:
        from_attributes = True

class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None
    section: str
    action: str

class PermissionCreate(PermissionBase):
    pass

class Permission(PermissionBase):
    id: int
    
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    email: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str
    role_names: Optional[List[str]] = []

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role_names: Optional[List[str]] = None

class UserChangePassword(BaseModel):
    current_password: str
    new_password: str

class User(UserBase):
    id: int
    created_at: datetime
    roles: List[Role] = []
    
    class Config:
        from_attributes = True

class UserWithPermissions(User):
    permissions: List[str] = []

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int