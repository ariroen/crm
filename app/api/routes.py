"""
Контракт-61: FastAPI маршруты (админ-панель / API).
"""
from datetime import datetime
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_session
from app.db.models import Candidate, Reminder, TicketStatus, MedicalStatus, TrainingStatus

app = FastAPI(title="Контракт-61: API", version="1.0.0")


@app.get("/")
async def root():
    return {"service": "Контракт-61: Диспетчер", "status": "operational", "time": datetime.now().isoformat()}


@app.get("/api/health")
async def health():
    from app.services.groq_service import groq_service
    groq_ok = await groq_service.health_check()
    return {"database": True, "groq_api": groq_ok}


@app.get("/api/candidates")
async def list_candidates(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Candidate).where(Candidate.archived == False).order_by(Candidate.created_at.desc())
    )
    candidates = result.scalars().all()
    return [
        {
            "id": c.id, "full_name": c.full_name, "phone": c.phone,
            "source": c.source, "ticket_status": c.ticket_status.value,
            "medical_status": c.medical_status.value, "training_status": c.training_status.value,
            "created_at": c.created_at.isoformat(),
        }
        for c in candidates
    ]


@app.get("/api/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    total = await session.scalar(select(func.count(Candidate.id)).where(Candidate.archived == False))
    return {
        "total_active": total or 0,
        "timestamp": datetime.now().isoformat(),
    }
