import logging

import asyncpg
import ujson

logger = logging.getLogger(__name__)


class DBProxy:
    pool = None

    async def pool_connection_init(self, conn):
        await conn.set_type_codec(
            'jsonb',
            encoder=ujson.dumps,
            decoder=ujson.loads,
            schema='pg_catalog'
        )

        await conn.set_type_codec(
            'json',
            encoder=ujson.dumps,
            decoder=ujson.loads,
            schema='pg_catalog'
        )

    async def initialize(self, app, loop, min_size=2, max_size=15):
        self.pool = await asyncpg.create_pool(
            database=app.config.DB_DATABASE,
            host=app.config.DB_HOST,
            port=app.config.DB_PORT,
            user=app.config.DB_USER,
            password=app.config.DB_PASSWORD,
            init=self.pool_connection_init,
            min_size=min_size,
            max_size=max_size,
            command_timeout=300,
            loop=loop
        )

    async def execute(self, *args, **kwargs):
        async with self.pool.acquire() as db:
            return await db.execute(*args, **kwargs)

    async def fetch(self, *args, **kwargs):
        async with self.pool.acquire() as db:
            return await db.fetch(*args, **kwargs)

    async def fetchrow(self, *args, **kwargs):
        async with self.pool.acquire() as db:
            return await db.fetchrow(*args, **kwargs)

    async def fetchval(self, *args, **kwargs):
        async with self.pool.acquire() as db:
            return await db.fetchval(*args, **kwargs)


db = DBProxy()
