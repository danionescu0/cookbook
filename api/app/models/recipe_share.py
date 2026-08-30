from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecipeShare(Base):
    """A private, expiring, person-to-person link for one recipe — distinct from
    Recipe.is_shared, which makes a recipe publicly browsable to everyone. See README Design
    Decisions ("Recipe sharing").

    Multi-use by design: anyone who has the token can view or copy the recipe (independently of
    anyone else who also has it) until it expires or the owner revokes it — there's no per-
    recipient claim/lock.
    """

    __tablename__ = "recipe_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when the owner cancels an outstanding link early — a soft delete (not a row delete) so
    # GET /recipes/{id}/shares can still show it as "revoked" in the sender's own history instead
    # of it just disappearing.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recipe: Mapped["Recipe"] = relationship()
