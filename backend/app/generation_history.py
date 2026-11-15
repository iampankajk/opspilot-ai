"""Shared exclusion/recovery helpers; callers hold the owned investigation row lock."""

from sqlalchemy import select

from app.models import AIGenerationRequest


def pending_generation(db, state_id):
    return (
        db.scalar(
            select(AIGenerationRequest.generation_id)
            .where(
                AIGenerationRequest.state_id == state_id,
                AIGenerationRequest.status == "pending",
            )
            .limit(1)
        )
        is not None
    )


def reconcile_generations(db, draft, clock):
    operations = db.scalars(
        select(AIGenerationRequest).where(
            AIGenerationRequest.state_id == draft.state_id,
            AIGenerationRequest.status == "pending",
            AIGenerationRequest.deadline_at <= clock(),
        )
    ).all()
    for operation in operations:
        operation.status = "interrupted"
        operation.failure_code = "AI_INTERRUPTED"
        operation.retryable = True
        operation.finished_at = max(clock(), operation.requested_at)
    return bool(operations)
