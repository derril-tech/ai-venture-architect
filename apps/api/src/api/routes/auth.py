"""Authentication endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    workspace_id: str


class RegisterRequest(BaseModel):
    """Registration request model."""
    email: EmailStr
    password: str
    full_name: str
    workspace_name: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """User login endpoint."""
    # TODO: Implement authentication logic
    return LoginResponse(
        access_token="dummy_token",
        user_id="dummy_user_id",
        workspace_id="dummy_workspace_id"
    )


@router.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    """User registration endpoint."""
    # TODO: Implement registration logic
    return LoginResponse(
        access_token="dummy_token",
        user_id="dummy_user_id",
        workspace_id="dummy_workspace_id"
    )


@router.post("/logout")
async def logout():
    """User logout endpoint."""
    return {"message": "Successfully logged out"}
