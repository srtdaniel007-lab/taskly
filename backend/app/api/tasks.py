import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_leader
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.task_update import TaskUpdate
from app.models.notification import Notification
from app.schemas.task import TaskCreate, TaskUpdate as TaskUpdateSchema, TaskStatusUpdate, TaskResponse, TaskMetricsResponse
from app.schemas.task_update import TaskUpdateCreate, TaskUpdateResponse
from app.services.email import send_email_async, get_task_assigned_email, get_task_update_email

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """
    Leader-only: Create a new task and assign to a team member.
    Triggers an in-app persistent notification and asynchronous email alert.
    """
    assignee = None
    if task_in.assignee_id:
        result = await db.execute(select(User).where(User.id == task_in.assignee_id))
        assignee = result.scalar_one_or_none()
        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignee user ID '{task_in.assignee_id}' does not exist."
            )

    task = Task(
        title=task_in.title,
        description=task_in.description,
        priority=task_in.priority,
        status=TaskStatus.TODO,
        leader_id=current_user.id,
        assignee_id=task_in.assignee_id,
        due_date=task_in.due_date
    )
    db.add(task)
    await db.flush()

    # Initial timeline entry
    timeline_entry = TaskUpdate(
        task_id=task.id,
        user_id=current_user.id,
        message=f"Task created by Leader {current_user.full_name}."
    )
    db.add(timeline_entry)

    # If assigned, trigger in-app notification & background email dispatch
    if assignee:
        notification = Notification(
            user_id=assignee.id,
            task_id=task.id,
            message=f"Leader {current_user.full_name} assigned you: '{task.title}' [{task.priority.value}]"
        )
        db.add(notification)

        due_date_str = task.due_date.strftime("%b %d, %Y %I:%M %p UTC") if task.due_date else "No due date specified"
        subj, txt, html = get_task_assigned_email(
            member_name=assignee.full_name,
            task_title=task.title,
            priority=task.priority.value,
            due_date_str=due_date_str,
            task_id=str(task.id)
        )
        background_tasks.add_task(
            send_email_async,
            to_email=assignee.email,
            subject=subj,
            text_content=txt,
            html_content=html
        )

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.leader), selectinload(Task.assignee), selectinload(Task.updates))
        .where(Task.id == task.id)
    )
    return result.scalar_one()


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    priority_filter: Optional[TaskPriority] = Query(None, alias="priority"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List tasks.
    Leaders see all created tasks (or team tasks).
    Members see their assigned tasks.
    """
    query = (
        select(Task)
        .options(
            selectinload(Task.leader),
            selectinload(Task.assignee),
            selectinload(Task.updates).selectinload(TaskUpdate.user)
        )
        .order_by(Task.created_at.desc())
    )

    if current_user.role == UserRole.MEMBER:
        query = query.where(Task.assignee_id == current_user.id)
    else:
        # Leader view: tasks created by this leader
        query = query.where(Task.leader_id == current_user.id)

    if status_filter:
        query = query.where(Task.status == status_filter)
    if priority_filter:
        query = query.where(Task.priority == priority_filter)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/metrics", response_model=TaskMetricsResponse)
async def get_task_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns live task aggregate counts by status for executive dashboard overview.
    """
    base_filter = Task.assignee_id == current_user.id if current_user.role == UserRole.MEMBER else Task.leader_id == current_user.id

    query = select(Task.status, func.count(Task.id)).where(base_filter).group_by(Task.status)
    result = await db.execute(query)
    counts = dict(result.all())

    return {
        "total": sum(counts.values()),
        "todo": counts.get(TaskStatus.TODO, 0),
        "seen": counts.get(TaskStatus.SEEN, 0),
        "in_progress": counts.get(TaskStatus.IN_PROGRESS, 0),
        "pending_review": counts.get(TaskStatus.PENDING_REVIEW, 0),
        "completed": counts.get(TaskStatus.COMPLETED, 0)
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_detail(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch task detail.
    Read Receipt: When an assigned member opens the task for the first time:
    - Auto-updates 'seen_at' timestamp
    - If status was 'TODO', auto-transitions to 'SEEN'
    - Creates audit timeline record
    - Notifies leader
    """
    query = (
        select(Task)
        .options(
            selectinload(Task.leader),
            selectinload(Task.assignee),
            selectinload(Task.updates).selectinload(TaskUpdate.user)
        )
        .where(Task.id == task_id)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Security check: User must be leader or assignee
    if current_user.role == UserRole.MEMBER and task.assignee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this task.")

    # Read Receipt Logic: Assignee opened for first time
    if current_user.role == UserRole.MEMBER and task.assignee_id == current_user.id and task.seen_at is None:
        now = datetime.now(timezone.utc)
        task.seen_at = now
        if task.status == TaskStatus.TODO:
            task.status = TaskStatus.SEEN

        # Add audit update
        receipt_update = TaskUpdate(
            task_id=task.id,
            user_id=current_user.id,
            message="Read receipt recorded: Member opened and acknowledged task."
        )
        db.add(receipt_update)

        # Notify leader
        notification = Notification(
            user_id=task.leader_id,
            task_id=task.id,
            message=f"{current_user.full_name} viewed task '{task.title}' at {now.strftime('%I:%M %p UTC')}."
        )
        db.add(notification)
        await db.commit()

        # Reload with updates
        result = await db.execute(query)
        task = result.scalar_one()

    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    task_update: TaskUpdateSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """
    Leader-only: Update task details, reassign, or sign off.
    """
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.leader), selectinload(Task.assignee), selectinload(Task.updates))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    old_assignee_id = task.assignee_id

    if task_update.title is not None:
        task.title = task_update.title
    if task_update.description is not None:
        task.description = task_update.description
    if task_update.priority is not None:
        task.priority = task_update.priority
    if task_update.due_date is not None:
        task.due_date = task_update.due_date
    if task_update.status is not None:
        task.status = task_update.status
    if task_update.assignee_id is not None:
        task.assignee_id = task_update.assignee_id

    # If newly reassigned
    if task_update.assignee_id and task_update.assignee_id != old_assignee_id:
        res = await db.execute(select(User).where(User.id == task_update.assignee_id))
        new_assignee = res.scalar_one_or_none()
        if new_assignee:
            notification = Notification(
                user_id=new_assignee.id,
                task_id=task.id,
                message=f"Leader {current_user.full_name} reassigned task '{task.title}' to you."
            )
            db.add(notification)
            due_str = task.due_date.strftime("%b %d, %Y") if task.due_date else "No due date"
            subj, txt, html = get_task_assigned_email(
                member_name=new_assignee.full_name,
                task_title=task.title,
                priority=task.priority.value,
                due_date_str=due_str,
                task_id=str(task.id)
            )
            background_tasks.add_task(send_email_async, to_email=new_assignee.email, subject=subj, text_content=txt, html_content=html)

    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: uuid.UUID,
    status_in: TaskStatusUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Transition task status:
    - Member: TODO -> IN_PROGRESS -> PENDING_REVIEW
    - Leader: PENDING_REVIEW -> COMPLETED (or request revisions -> IN_PROGRESS)
    Triggers timeline update, in-app notification, and email to counterpart.
    """
    query = (
        select(Task)
        .options(
            selectinload(Task.leader),
            selectinload(Task.assignee),
            selectinload(Task.updates).selectinload(TaskUpdate.user)
        )
        .where(Task.id == task_id)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    old_status = task.status
    new_status = status_in.status

    # Role validation
    if current_user.role == UserRole.MEMBER:
        if task.assignee_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update status of unassigned task.")
        if new_status == TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Members cannot sign off directly as COMPLETED. Submit as PENDING_REVIEW for Leader sign-off."
            )

    task.status = new_status

    # Record in audit trail
    timeline_message = f"Status changed from {old_status.value} to {new_status.value} by {current_user.full_name} ({current_user.role.value})."
    if status_in.note:
        timeline_message += f"\nNote: {status_in.note}"

    db.add(TaskUpdate(
        task_id=task.id,
        user_id=current_user.id,
        message=timeline_message
    ))

    # Leader Verification Loop notifications:
    # If member requests review (PENDING_REVIEW) -> Alert Leader
    if current_user.role == UserRole.MEMBER and new_status == TaskStatus.PENDING_REVIEW:
        leader_notif = Notification(
            user_id=task.leader_id,
            task_id=task.id,
            message=f"Review Requested: {current_user.full_name} submitted '{task.title}' for verification."
        )
        db.add(leader_notif)

        subj, txt, html = get_task_update_email(
            leader_name=task.leader.full_name,
            task_title=task.title,
            member_name=current_user.full_name,
            action_type="Submitted For Review",
            details=status_in.note or "Work completed and submitted for leader verification.",
            task_id=str(task.id)
        )
        background_tasks.add_task(
            send_email_async,
            to_email=task.leader.email,
            subject=subj,
            text_content=txt,
            html_content=html
        )

    # If leader completed or requested revisions -> Alert Member
    elif current_user.role == UserRole.LEADER and task.assignee:
        action_name = "Approved & Completed" if new_status == TaskStatus.COMPLETED else f"Status updated to {new_status.value}"
        member_notif = Notification(
            user_id=task.assignee.id,
            task_id=task.id,
            message=f"Leader {current_user.full_name} set '{task.title}' to {new_status.value}."
        )
        db.add(member_notif)

        subj, txt, html = get_task_update_email(
            leader_name=task.assignee.full_name,
            task_title=task.title,
            member_name=f"Leader {current_user.full_name}",
            action_type=action_name,
            details=status_in.note or f"Task marked as {new_status.value}.",
            task_id=str(task.id)
        )
        background_tasks.add_task(
            send_email_async,
            to_email=task.assignee.email,
            subject=subj,
            text_content=txt,
            html_content=html
        )

    await db.commit()

    # Re-fetch task
    result = await db.execute(query)
    return result.scalar_one()


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """
    Leader-only: Delete a task and associated updates/notifications.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return None


@router.post("/{task_id}/updates", response_model=TaskUpdateResponse, status_code=status.HTTP_201_CREATED)
async def add_task_update(
    task_id: uuid.UUID,
    update_in: TaskUpdateCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a progress note, deliverable link, or comment to a task's audit trail.
    Alerts counterpart with in-app notification and email.
    """
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.leader), selectinload(Task.assignee))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Create comment / update record
    update = TaskUpdate(
        task_id=task.id,
        user_id=current_user.id,
        message=update_in.message,
        attachment_url=update_in.attachment_url
    )
    db.add(update)

    # Determine recipient for notification
    if current_user.role == UserRole.MEMBER and task.leader:
        recipient = task.leader
        notif_msg = f"{current_user.full_name} posted an update on '{task.title}': {update_in.message[:80]}"
    elif current_user.role == UserRole.LEADER and task.assignee:
        recipient = task.assignee
        notif_msg = f"Leader {current_user.full_name} posted on '{task.title}': {update_in.message[:80]}"
    else:
        recipient = None
        notif_msg = None

    if recipient and notif_msg:
        db.add(Notification(
            user_id=recipient.id,
            task_id=task.id,
            message=notif_msg
        ))
        subj, txt, html = get_task_update_email(
            leader_name=recipient.full_name,
            task_title=task.title,
            member_name=current_user.full_name,
            action_type="New Progress Note",
            details=update_in.message + (f"\nAttachment: {update_in.attachment_url}" if update_in.attachment_url else ""),
            task_id=str(task.id)
        )
        background_tasks.add_task(
            send_email_async,
            to_email=recipient.email,
            subject=subj,
            text_content=txt,
            html_content=html
        )

    await db.commit()

    # Return with author details loaded
    res = await db.execute(
        select(TaskUpdate).options(selectinload(TaskUpdate.user)).where(TaskUpdate.id == update.id)
    )
    return res.scalar_one()


@router.get("/{task_id}/updates", response_model=List[TaskUpdateResponse])
async def list_task_updates(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve chronological activity and audit trail for a task.
    """
    result = await db.execute(
        select(TaskUpdate)
        .options(selectinload(TaskUpdate.user))
        .where(TaskUpdate.task_id == task_id)
        .order_by(TaskUpdate.created_at.asc())
    )
    return result.scalars().all()

