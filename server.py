import logging
import asyncio
import os
import uuid

import aiohttp
import scipy
from transformers import AutoProcessor, MusicgenForConditionalGeneration

from httpclient import request
from settings import settings
from tgclient import tgclient

processor = AutoProcessor.from_pretrained('facebook/musicgen-small')
model = MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-small')


async def generate(order):
    inputs = processor(
        text=[' '.join(order['words'])],
        padding=True,
        return_tensors='pt',
    )

    uid = str(uuid.uuid4())
    root_dir = settings['root_dir'] + '/static/uploads/' + f'{uid[:2]}/{uid[2:4]}'
    if not os.path.isdir(root_dir):
        os.makedirs(root_dir)

    audio_values = model.generate(**inputs, max_new_tokens=1024)
    sampling_rate = model.config.audio_encoder.sampling_rate
    scipy.io.wavfile.write(f'{root_dir}/{uid}.mp3', rate=sampling_rate, data=audio_values[0, 0].numpy())

    form_data = aiohttp.FormData()
    form_data.add_field('file', open(f'{root_dir}/{uid}.mp3', 'rb'))

    success, data = await request(
        method='post',
        url='https://art.ttshop.kz/api/upload/',
        data=form_data
    )

    if success and data and data.get('_success'):
        await tgclient.api_call(
            method_name='sendAudio',
            payload={
                'chat_id': order['chat_id'],
                'audio': f'https://art.ttshop.kz/static/uploads/{data["file_name"]}'
            }
        )
    else:
        await tgclient.api_call(
            method_name='sendMessage',
            payload={
                'chat_id': order['chat_id'],
                'text': 'error'
            }
        )


async def main():
    while True:
        success, data = await request(
            method='get',
            url='https://art.ttshop.kz/orders?action=get_orders'
        )

        if success and data and data.get('_success'):
            if not data.get('order'):
                await asyncio.sleep(15)
                continue

            logging.debug('main stat generate')
            loop.create_task(generate(data['order']))

        await asyncio.sleep(15)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
