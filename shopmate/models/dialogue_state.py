from sqlalchemy import String, Text
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
