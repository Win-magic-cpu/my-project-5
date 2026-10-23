from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shopmate.models.base import Base


class DialogueStateRecord(Base):
    __tablename__ = "dialogue_states"

    sender_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    state_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # 乐观锁版本号：每次成功保存 +1
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
