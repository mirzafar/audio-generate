import asyncio

from cache import cache
from db import db
from replicate import Client

from settings import settings
from tgclient import tgclient


class App:
    class Config:
        ACCESS_LOG = False
        DB_HOST = settings.get('db', {}).get('host', '127.0.0.1')
        DB_DATABASE = settings.get('db', {}).get('database', 'kenes')
        DB_PORT = settings.get('db', {}).get('port', 5432)
        DB_USER = settings.get('db', {}).get('user', 'root')
        DB_PASSWORD = settings.get('db', {}).get('password', 'X$@ABN^')
        DB_USE_CONNECTION_FOR_REQUEST = False
        DB_POOL_MAX_SIZE = 25

    def __init__(self):
        self.config = App.Config()


async def main():
    client = Client(api_token='r8_agYdIyP42udjzCiMulRpAEdB4jLPrvw2DbB8v')
    await db.initialize(App(), loop)
    await cache.initialize(loop)

    while True:
        playlist = await db.fetchrow(
            '''
            SELECT p.*, c.uid AS chat_id
            FROM public.playlist p
            LEFT JOIN public.customers c ON c.id = p.customer_id
            WHERE p.status = 0 AND p.words IS NOT NULL
            '''
        )

        if playlist:
            await db.fetchrow(
                '''
                UPDATE public.playlist
                SET status = 1
                WHERE id = $1
                ''',
                playlist['id'],
            )
            loop.create_task(generate(playlist, client))

        await asyncio.sleep(5)


async def generate(playlist, client):
    try:
        output = await client.async_run(
            'meta/musicgen:b05b1dff1d8c6dc63d14b0cdb42135378dcb87f6373b0d3d341ede46e59e2b38',
            input={
                'top_k': 250,
                'top_p': 0,
                'prompt': ', '.join(playlist['words']),
                'duration': 15,
                'temperature': 1,
                'continuation': False,
                'model_version': 'stereo-large',
                'output_format': 'mp3',
                'continuation_start': 0,
                'multi_band_diffusion': False,
                'normalization_strategy': 'peak',
                'classifier_free_guidance': 3
            }
        )

    except (Exception,):
        tune = await db.fetchrow(
            '''
            SELECT *
            FROM public.tunes
            ORDER BY (
                SELECT COUNT(*)
                FROM unnest(words) AS element1
                INNER JOIN unnest($1::text[]) AS element2 ON element1 = element2
            ) DESC
            LIMIT 1;
            ''',
            list(set(playlist['words']))
        )

        output = settings['base_url'] + '/static/uploads/' + tune['path'] if tune else None

    if not output:
        await db.fetchrow(
            '''
            UPDATE public.playlist
            SET status = 2
            WHERE id = $1
            ''',
            playlist['id']
        )

        return await tgclient.api_call(
            method_name='sendMessage',
            payload={
                'chat_id': playlist['chat_id'],
                'text': 'Ничего не найдено',
                'reply_markup': {
                    'keyboard': [[{
                        'text': '🏠 Вернуться в меню',
                    }]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True
                }
            }
        )

    await cache.setex(f'art:telegram:audio:{playlist["customer_id"]}', 600, playlist['id'])
    await tgclient.api_call(
        method_name='sendAudio',
        payload={
            'chat_id': playlist['chat_id'],
            'audio': output,
            'reply_markup': {
                'keyboard': [
                    [{'text': '\u2069Сохранить трек'}],
                    [{
                        'text': '🏠 Вернуться в меню',
                    }]
                ],
                'one_time_keyboard': True,
                'resize_keyboard': True
            }
        }
    )

    await db.fetchrow(
        '''
        UPDATE public.playlist
        SET status = 2, url = $2
        WHERE id = $1
        ''',
        playlist['id'],
        str(output)
    )


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
