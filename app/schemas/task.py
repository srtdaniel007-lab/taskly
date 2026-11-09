import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.task import TaskPriority, TaskStatus
from app.schemas.user import UserResponse
from app.schemas.task_update import TaskUpdateResponse


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    assignee_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[datetime] = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    note: Optional[str] = None


class TaskResponse(TaskBase):
    id: uuid.UUID
    status: TaskStatus
    leader_id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = None
    seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    leader: Optional[UserResponse] = None
    assignee: Optional[UserResponse] = None
    updates: Optional[List[TaskUpdateResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class TaskMetricsResponse(BaseModel):
    total: int
    todo: int
    seen: int
    in_progress: int
    pending_review: int
    completed: int
