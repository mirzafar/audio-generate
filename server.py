import asyncio
import os
import uuid

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

    await tgclient.api_call(
        method_name='sendPhoto',
        payload={
            'chat_id': order['chat_id'],
            'photo': f'{settings["base_url"]}/static/uploads/{uid[:2]}/{uid[2:4]}/{uid}.mp3'
        }
    )

    await request(
        method='POST',
        url='https://art.ttshop.kz/orders/',
        json={
            'action': 'done',
            'order': {
                'id': order['id'],
                'path': f'{uid[:2]}/{uid[2:4]}/{uid}.mp3'
            }
        }
    )


async def main():
    while True:
        success, data = await request(
            method='GET',
            url='https://art.ttshop.kz/orders?action=get_orders'
        )

        if success and data and data.get('_success'):
            if not data.get('order'):
                await asyncio.sleep(2)
                continue

            print('main stat generate')
            loop.create_task(generate(data['order']))
            await asyncio.sleep(2)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
