import asyncio

from random import randint
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from config.logger import logger
from config.db import async_session_injector
from utils.cruds import FoodCRUD, UserCRUD, StatCRUD


CAT_SATIETY_PERIOD = 60
CAT_TIME_TO_FORGET = 300


def get_weights(n: int) -> list[float]:
    summ = sum([1 / (pow(2, i + 1)) for i in range(n)])
    weights = [1 / (pow(2, i + 1)) / summ for i in range(n)]
    return weights


class Cat:
    def __init__(self):
        self._satiety_period = CAT_SATIETY_PERIOD
        self._time_to_forget = CAT_TIME_TO_FORGET
        self._satiety_scale = 0.0
        self._pet_scale = 0.0

        asyncio.create_task(self._monitoring_self_scales())

    @async_session_injector
    async def _get_satiety_scale(self, session: AsyncSession) -> float:
        results = await StatCRUD.get_eat_stat_for_the_last_period(
            self._satiety_period, session=session
        )
        if not results:
            logger.debug("satiety_scale: 0.0")
            return 0.0
        n = len(results)
        current_time = datetime.utcnow()
        weights = [
            (
                self._satiety_period
                - (current_time - el.eaten_at).total_seconds()
            )
            / self._satiety_period
            for el in results
        ]
        weights = [el / sum(weights) for el in weights]
        points = [
            weights[i] * (results[i].is_success or results[i].is_cat_was_fed)
            for i in range(n)
        ]
        scale = sum(points)
        logger.debug(f"satiety_scale: {scale}")
        return scale

    @async_session_injector
    async def _get_pet_scale(self, session: AsyncSession):
        results = await StatCRUD.get_pet_stat_for_the_last_period(
            self._time_to_forget, session=session
        )
        if not results:
            logger.debug("pet_scale: 0.0")
            return 0.0
        n = len(results)
        weights = get_weights(n)
        points = [weights[i] * results[i] for i in range(n)]
        scale = sum(points)
        logger.debug("pet_scale:", scale)
        return scale

    async def _monitoring_self_scales(self):
        while True:
            self._satiety_scale = await self._get_satiety_scale()
            self._pet_scale = await self._get_pet_scale()
            await asyncio.sleep(1)

    @property
    def happiness_scale(self) -> float:
        scale = (
            0.5 * self._satiety_scale
            + 0.3 * self._pet_scale
            + 0.2 * randint(1, 100) / 100
        )
        print("happiness_scale:", scale)
        return scale
