from config.db import Base

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    DateTime,
    func,
)


_id = Column(Integer, primary_key=True, index=True, autoincrement=True)


class User(Base):
    __tablename__ = "user"
    id = _id
    name = Column(String, unique=True, nullable=False)


class Food(Base):
    __tablename__ = "food"
    id = _id
    name = Column(String, unique=True, nullable=False)
    preferred_by_the_cat = Column(Boolean, nullable=False)


class EatStat(Base):
    __tablename__ = "eat_stat"
    id = _id
    user_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    food_id = Column(
        Integer, ForeignKey("food.id", ondelete="CASCADE"), nullable=False
    )
    is_success = Column(Boolean, nullable=False)
    is_cat_was_fed = Column(Boolean, nullable=False)
    eat_at = Column(DateTime, default=func.now())


class PetStat(Base):
    __tablename__ = "pet_stat"
    id = _id
    user_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    is_success = Column(Boolean, nullable=False)
    pet_at = Column(DateTime, default=func.now())
