import datetime
from typing import List

from sqlalchemy import select, and_, desc, update, Select, Update
from sqlalchemy.dialects.postgresql import insert, Insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Food, EatStat, PetStat


class CRUD:
    def __init__(self, model):
        self._model = model

    @property
    def _select_model(self) -> Select:
        return select(self._model)

    @property
    def _insert_model(self) -> Insert:
        return insert(self._model)

    @property
    def _update_model(self) -> Update:
        return update(self._model)


class _UserCRUD(CRUD):
    def __init__(self):
        super().__init__(User)

    async def add_new_user(self, name: str, session: AsyncSession) -> int:
        query = (
            self._insert_model.values({"name": name})
            .returning(self._model.id)
            .on_conflict_do_nothing()
        )
        id = (await session.execute(query)).scalar()
        await session.commit()
        return id

    async def get_user(self, name: str, session: AsyncSession) -> User:
        query = self._select_model.where(self._model.name == name)
        res = (await session.execute(query)).scalar()
        return res


class _FoodCRUD(CRUD):
    def __init__(self):
        super().__init__(Food)

    async def add_new_food(
        self, name: str, prefered_by_the_cat, session: AsyncSession
    ) -> int:
        query = (
            self._insert_model.values(
                {"name": name, "preferred_by_the_cat": prefered_by_the_cat}
            )
            .returning(self._model.id)
            .on_conflict_do_nothing()
        )
        id = (await session.execute(query)).scalar()
        await session.commit()
        return id

    async def get_food(self, name: str, session) -> Food:
        query = self._select_model.where(self._model.name == name)
        res = (await session.execute(query)).scalar()
        return res

    async def is_food_preferred_by_the_cat(
        self, name: str, session: AsyncSession
    ) -> bool:
        query = select(self._model.preferred_by_the_cat).where(
            Food.name == name
        )
        res = (await session.execute(query)).scalar()
        if not res:
            return False
        return res


class StatCRUD:
    @staticmethod
    async def get_eat_stat_by_username_and_period(
        name: str, period: float, session: AsyncSession
    ) -> List[EatStat]:
        query = (
            select(EatStat)
            .join(User, and_(User.id == EatStat.user_id, User.name == name))
            .where(
                EatStat.eaten_at
                >= datetime.datetime.utcnow()
                - datetime.timedelta(seconds=period)
            )
            .order_by(desc(EatStat.eaten_at))
        )
        res = (await session.execute(query)).scalars().all()
        return res

    @staticmethod
    async def get_pet_stat_by_username_and_period(
        name: str, period: float, session: AsyncSession
    ) -> List[PetStat]:
        query = (
            select(PetStat)
            .join(User, and_(User.id == PetStat.user_id, User.name == name))
            .where(
                PetStat.pet_at
                >= datetime.datetime.utcnow()
                - datetime.timedelta(seconds=period)
            )
            .order_by(desc(PetStat.pet_at))
        )
        res = (await session.execute(query)).scalars().all()
        return res

    @staticmethod
    async def get_eat_stat_for_the_last_period(
        period: float, session: AsyncSession
    ) -> List[EatStat]:
        query = select(EatStat).where(
            EatStat.eaten_at
            >= datetime.datetime.utcnow() - datetime.timedelta(seconds=period)
        )
        res = (await session.execute(query)).scalars().all()
        return res

    @staticmethod
    async def get_pet_stat_for_the_last_period(
        period: float, session: AsyncSession
    ) -> List[PetStat]:
        query = select(PetStat.is_success).where(
            PetStat.pet_at
            >= datetime.datetime.utcnow() - datetime.timedelta(seconds=period)
        )
        res = (await session.execute(query)).scalars().all()
        return res

    @staticmethod
    async def add_eat_stat(
        user_id: int,
        food_id: int,
        is_success: bool,
        is_cat_was_fed: bool,
        session: AsyncSession,
    ) -> int:
        query = (
            insert(EatStat)
            .values(
                {
                    "user_id": user_id,
                    "food_id": food_id,
                    "is_success": is_success,
                    "is_cat_was_fed": is_cat_was_fed,
                }
            )
            .returning(EatStat.id)
        )
        id = (await session.execute(query)).scalar()
        await session.commit()
        return id

    @staticmethod
    async def add_pet_stat(
        user_id: int, is_success: bool, session: AsyncSession
    ) -> int:
        query = (
            insert(PetStat)
            .values({"user_id": user_id, "is_success": is_success})
            .returning(PetStat.id)
        )
        id = (await session.execute(query)).scalar()
        await session.commit()
        return id


UserCRUD = _UserCRUD()
FoodCRUD = _FoodCRUD()
