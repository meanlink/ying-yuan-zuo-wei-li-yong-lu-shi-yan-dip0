from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..models import now_utc


class SubsidyPool(Base):
    """周末试行补贴池：全排片版本共用一份总额和每座标准。"""
    __tablename__ = 'subsidy_pools'
    __table_args__ = (
        CheckConstraint('total_cents >= 0 AND per_seat_cents > 0'),
        CheckConstraint('reserved_cents >= 0 AND charged_cents >= 0'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    per_seat_cents: Mapped[int] = mapped_column(Integer)
    reserved_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    charged_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class SubsidyReservation(Base):
    """每张试行工单的补贴占用台账，每座标准快照自派单时刻。"""
    __tablename__ = 'subsidy_reservations'
    __table_args__ = (
        UniqueConstraint('pilot_id'),
        CheckConstraint("state IN ('reserved','charged','released')"),
        CheckConstraint('reserved_cents > 0 AND per_seat_cents > 0'),
        CheckConstraint('charged_cents IS NULL OR charged_cents >= 0'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    pilot_id: Mapped[int] = mapped_column(ForeignKey('scheduling_pilots.id'), index=True)
    per_seat_cents: Mapped[int] = mapped_column(Integer)
    reserved_cents: Mapped[int] = mapped_column(BigInteger)
    charged_cents: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16), default='reserved')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
