from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/members", response_model=List[UserResponse])
async def list_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all registered members (available for task assignment).
    """
    result = await db.execute(
        select(User).where(User.role == UserRole.MEMBER).order_by(User.full_name.asc())
    )
    return result.scalars().all()


@router.get("/leaders", response_model=List[UserResponse])
async def list_leaders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all registered team leaders.
    """
    result = await db.execute(
        select(User).where(User.role == UserRole.LEADER).order_by(User.full_name.asc())
    )
    return result.scalars().all()
