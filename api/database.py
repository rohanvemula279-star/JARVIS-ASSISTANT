from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker # pyre-ignore[21]
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column # pyre-ignore[21]
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text # pyre-ignore[21]
from datetime import datetime
from api.config import settings # pyre-ignore[21]

# Database Engine
engine = create_async_engine(settings.DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    device_id: Mapped[str] = mapped_column(String)
    device_name: Mapped[str | None] = mapped_column(String)
    refresh_token_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ip_address: Mapped[str | None] = mapped_column(String)

class ActionHistory(Base):
    __tablename__ = "action_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String, ForeignKey("sessions.id"))
    action_type: Mapped[str] = mapped_column(String)
    input_text: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)  # 'success', 'error', 'timeout'
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with SessionLocal() as session:
        yield session
