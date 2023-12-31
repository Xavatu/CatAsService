import asyncio
import re

from random import randint
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from application.network.server import (
    AsyncTcpServer,
    AsyncUdpServer,
    AsyncTcpConnection,
    AsyncUdpConnection,
)
from application.utils.cruds import FoodCRUD, UserCRUD, StatCRUD
from config.logger import logger
from config.db import async_session_injector


CAT_SATIETY_PERIOD = 60
CAT_TIME_TO_FORGET = 300

host = "127.0.0.1"
tcp_port = 8000
udp_port = 8001

tcp_response_messages = {
    False: b"Scratched by the Cat",
    True: b"Tolerated by the Cat",
}

udp_response_messages = {
    False: b"Ignored by the Cat",
    True: b"Eaten by the Cat",
}


def get_weights(n: int) -> list[float]:
    summ = sum([1 / (pow(2, i + 1)) for i in range(n)])
    weights = [1 / (pow(2, i + 1)) / summ for i in range(n)]
    return weights


class Cat:
    def __init__(self):
        self._satiety_period = CAT_SATIETY_PERIOD
        self._time_to_forget = CAT_TIME_TO_FORGET
        self._satiety_scale = 0.0
        self._pet_scale = 1.0
        self._started = False

        asyncio.create_task(self._monitoring_self_scales())

    @property
    def started(self):
        return self._started

    @async_session_injector
    async def _get_satiety_scale(self, session: AsyncSession) -> float:
        results = await StatCRUD.get_eat_stat_for_the_last_period(
            self._satiety_period, session=session
        )
        if not results:
            # logger.debug("satiety_scale: 0.0")
            return 0.0
        n = len(results)
        current_time = datetime.utcnow()
        weights = [
            (self._satiety_period - (current_time - el.eat_at).total_seconds())
            / self._satiety_period
            for el in results
        ]
        weights = [el / sum(weights) for el in weights]
        points = [
            weights[i] * (results[i].is_success or results[i].is_cat_was_fed)
            for i in range(n)
        ]
        scale = sum(points)
        # logger.debug(f"satiety_scale: {scale}")
        return scale

    @async_session_injector
    async def _get_pet_scale(self, session: AsyncSession):
        results = await StatCRUD.get_pet_stat_for_the_last_period(
            self._time_to_forget, session=session
        )
        if not results:
            # logger.debug("pet_scale: 0.0")
            return 0.0
        n = len(results)
        weights = get_weights(n)
        points = [weights[i] * results[i] for i in range(n)]
        scale = sum(points)
        # logger.debug(f"pet_scale: {scale}")
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
        logger.debug(f"happiness_scale: {scale}")
        return scale

    @property
    def satiety_scale(self) -> float:
        return self._satiety_scale

    @property
    def pet_scale(self) -> float:
        return self._pet_scale

    @async_session_injector
    async def _predisposition_by_eat_scale(
        self, username: str, session: AsyncSession
    ) -> float:
        results = await StatCRUD.get_eat_stat_by_username_and_period(
            username, self._time_to_forget, session=session
        )
        if not results:
            logger.debug("_predisposition_by_eat_scale: 1.0")
            return 1.0
        n = len(results)
        weights = get_weights(n)
        points = [
            weights[i] * (results[i].is_success or results[i].is_cat_was_fed)
            for i in range(n)
        ]
        scale = sum(points)
        logger.debug(f"_predisposition_by_eat_scale: {scale}")
        return scale

    @async_session_injector
    async def _predisposition_by_pet_scale(
        self, username: str, session: AsyncSession
    ) -> float:
        results = await StatCRUD.get_pet_stat_by_username_and_period(
            username, self._time_to_forget, session=session
        )
        if not results:
            logger.debug("predisposition_by_pet_scale: 1.0")
            return 1
        n = len(results)
        weights = get_weights(n)
        points = [weights[i] * results[i].is_success for i in range(n)]
        scale = sum(points)
        logger.debug(f"predisposition_by_pet_scale: {scale}")
        return scale

    @async_session_injector
    async def predisposition_to_eat(
        self, username: str, session: AsyncSession
    ) -> float:
        scale = (
            0.2 * self.happiness_scale
            + 0.5 * (1 - self._satiety_scale)
            + 0.2
            * await self._predisposition_by_eat_scale(
                username, session=session
            )
            + 0.1
            * await self._predisposition_by_pet_scale(
                username, session=session
            )
        )
        logger.debug("predisposition_to_eat: {scale}")
        return scale

    @async_session_injector
    async def predisposition_to_pet(
        self, username: str, session: AsyncSession
    ) -> float:
        scale = (
            0.75 * self.happiness_scale
            + 0.2
            * await self._predisposition_by_eat_scale(
                username, session=session
            )
            + 0.05
            * await self._predisposition_by_pet_scale(
                username, session=session
            )
        )
        logger.debug("predisposition_to_pet: {scale}")
        return scale

    @async_session_injector
    async def _does_the_cat_know_the_human(
        self, username: str, session: AsyncSession
    ) -> UserCRUD.model | None:
        user = await UserCRUD.get_user(username, session=session)
        logger.debug(f"does_the_cat_know_the_human: {user}")
        return user

    @async_session_injector
    async def _does_the_cat_tried_this_food(
        self, foodname: str, session: AsyncSession
    ) -> FoodCRUD.model | None:
        food = await FoodCRUD.get_food(foodname, session=session)
        logger.debug(f"does_the_cat_tried_this_food: {food}")
        return food

    @async_session_injector
    async def _does_the_cat_likes_this_food(
        self, foodname: str, session: AsyncSession
    ) -> bool:
        is_preffered = await FoodCRUD.is_food_preferred_by_the_cat(
            foodname, session=session
        )
        logger.debug(f"does_the_cat_likes_this_food: {is_preffered}")
        return is_preffered

    @async_session_injector
    async def feed(
        self, username: str, foodname: str, session: AsyncSession
    ) -> bool:
        self._started = True
        if not (
            user := await self._does_the_cat_know_the_human(
                username, session=session
            )
        ):
            user = await UserCRUD.add_new_user(username, session=session)
        if not (
            food := await self._does_the_cat_tried_this_food(
                foodname, session=session
            )
        ):
            food = await FoodCRUD.add_new_food(
                name=foodname,
                prefered_by_the_cat=randint(0, 1),
                session=session,
            )
        pre_result = food.preferred_by_the_cat
        scale = pre_result * await self.predisposition_to_eat(
            username, session=session
        )
        is_cat_fed = self.satiety_scale > 0.75
        logger.debug(f"satiety_scale: {self.satiety_scale}")
        if scale > 0.5:
            await StatCRUD.add_eat_stat(
                user_id=user.id,
                food_id=food.id,
                is_success=True,
                is_cat_was_fed=is_cat_fed,
                session=session,
            )
            logger.debug(f"fed successfully: {scale}")
            return True
        await StatCRUD.add_eat_stat(
            user_id=user.id,
            food_id=food.id,
            is_success=False,
            is_cat_was_fed=is_cat_fed,
            session=session,
        )
        logger.debug(f"fed unsuccessfully: {scale}")
        return False

    @async_session_injector
    async def pet(self, name: str, session: AsyncSession) -> bool:
        self._started = True
        if not (
            user := await self._does_the_cat_know_the_human(
                name, session=session
            )
        ):
            user = await UserCRUD.add_new_user(name, session=session)
        scale = await self.predisposition_to_pet(name, session=session)
        if scale > 0.5:
            await StatCRUD.add_pet_stat(user.id, True, session=session)
            logger.debug(f"pet successfully: {scale}")
            return True
        await StatCRUD.add_pet_stat(user.id, False, session=session)
        logger.debug(f"pet unsuccessfully: {scale}")
        return False


class CatService:
    def __init__(self):
        self._cat = Cat()
        self._tcp_server = AsyncTcpServer(host, tcp_port)
        self._udp_server = AsyncUdpServer(host, udp_port)

    async def _start_servers(self):
        await asyncio.gather(
            self._tcp_server.start(), self._udp_server.start()
        )

    async def _stop_servers(self):
        await asyncio.gather(self._tcp_server.stop(), self._udp_server.stop())

    async def _tcp_response(self, connection: AsyncTcpConnection, data: bytes):
        await connection.write(data)
        logger.debug(f"{data.decode()} -> {connection}")

    def _data_preprocessing(
        self, connection, received_data: bytes, regex: str
    ) -> list[str]:
        incorrect_data = False
        message = received_data.decode()
        corrupted_word = connection.buffer.decode()
        names = []
        found = [el for el in re.findall(regex, message) if el]
        words = [el for el in re.split(regex, message) if el]

        for word in words:
            if "@" in word or "~" in word or corrupted_word:
                corrupted_word += word
                if "~" not in word:
                    break
                elif "~" != word[-1]:
                    logger.warning("Incorrect data")
                    raise ValueError("Incorrect data")
                word = re.match(regex, corrupted_word)
                word = word.group(1) if word else None
                if not word:
                    incorrect_data = True
                    corrupted_word = ""
                    break
                corrupted_word = ""
            names.append(word)

        logger.info(f"{names=}")
        logger.info(f"{corrupted_word=}")
        connection.buffer = corrupted_word.encode()
        if incorrect_data:
            raise ValueError("Incorrect data")
        return names

    async def _tcp_data_processing(
        self, connection: AsyncTcpConnection, received_data: bytes
    ) -> bytes:
        result = b""
        try:
            names = self._data_preprocessing(
                connection, received_data, regex="@([^@~]+)~"
            )
        except ValueError:
            return b"Incorrect data"

        for name in names:
            result += tcp_response_messages[await self._cat.pet(name)]

        if self._cat.happiness_scale < 0.2:
            await connection.close()

        return result

    async def _handle_tcp_requests(self):
        logger.debug("tcp handler started")
        while True:
            await asyncio.sleep(0.1)
            for connection in self._tcp_server.connections:
                try:
                    data = await asyncio.wait_for(
                        connection.read(100), timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue
                except ConnectionError:
                    # logger.debug(f"{connection} closed")
                    continue
                logger.debug(f"{connection} -> {data.decode()}")
                response = await self._tcp_data_processing(connection, data)
                try:
                    await self._tcp_response(connection, response)
                except ConnectionError:
                    continue

    async def _udp_response(self, connection: AsyncUdpConnection, data: bytes):
        await connection.write(data)
        logger.debug(f"{data.decode()} -> {connection}")

    async def _udp_data_processing(
        self, connection: AsyncUdpConnection, received_data: bytes
    ) -> bytes:
        result = b""
        try:
            names = self._data_preprocessing(
                connection, received_data, regex="@([^@~]+)~"
            )
        except ValueError:
            return b"Incorrect data"

        lists = [list(name.split(" - ")) for name in names]
        logger.info(f"{lists=}")

        for lst in lists:
            logger.warning(lst)
            try:
                name = lst[0]
            except IndexError:
                logger.warning("Incorrect data")
                result += b"Incorrect data"
                continue
            try:
                foodname = lst[1]
            except IndexError:
                logger.warning("Incorrect data")
                result += b"Incorrect data"
                continue
            result += udp_response_messages[
                await self._cat.feed(name, foodname)
            ]

        if connection.buffer:
            print(connection.buffer)
            result += f"The Cat is amused by #{connection.counter}".encode()
            connection.counter += 1
        else:
            connection.counter = 0

        return result

    async def _handle_udp_requests(self):
        logger.debug("udp handler started")
        while True:
            await asyncio.sleep(1)
            for connection in self._udp_server.connections:
                if not connection.message_buffer:
                    continue
                data = connection.message_buffer
                connection.message_buffer = b""
                # logger.debug(f"{connection} -> {data.decode()}")
                response = await self._udp_data_processing(connection, data)
                try:
                    await self._udp_response(connection, response)
                except ConnectionError:
                    continue

    async def _start_handlers(self):
        await asyncio.gather(
            self._handle_tcp_requests(), self._handle_udp_requests()
        )

    async def start(self):
        await asyncio.gather(self._start_servers(), self._start_handlers())

    async def stop(self):
        logger.info("Stop CatService")
        await asyncio.gather(self._stop_servers())


if __name__ == "__main__":

    async def main():
        cat_service = CatService()
        await cat_service.start()
        logger.info("CatService was stopped")
        # await cat_service._stop()

    asyncio.run(main())
