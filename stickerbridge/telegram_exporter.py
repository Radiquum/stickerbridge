from multiprocessing import Pool
from typing import List

import logging
from tqdm.auto import tqdm

from lottie.importers import importers
from lottie.exporters import exporters
from telethon import TelegramClient
from telethon.errors import StickersetInvalidError
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName

from io import BytesIO
from PIL import Image

from sticker_types import Sticker


def _convert_image(data: bytes):
    image: Image.Image = Image.open(BytesIO(data)).convert("RGBA")
    new_file = BytesIO()
    image.save(new_file, "png")
    w, h = image.size
    if w > 256 or h > 256:
        if w > h:
            h = int(h / (w / 256))
            w = 256
        else:
            w = int(w / (h / 256))
            h = 256
    return new_file.getvalue(), w, h, "image/png"


def _convert_animation(data: bytes, width=256, height=0):
    importer = importers.get_from_extension('tgs')
    exporter = exporters.get('webp')
    an = importer.process(BytesIO(data))

    an.frame_rate = 24

    if width or height:
        if not width:
            width = an.width * height / an.height
        if not height:
            height = an.height * width / an.width
        an.scale(width, height)

    out = BytesIO()
    exporter.process(an, out)
    return out.getvalue(), width, height, "image/webp"


def _process_sticker(document) -> Sticker:
    alt: str = document.attributes[1].alt
    if document.mime_type == 'image/webp':
        data, width, height, mime_type = _convert_image(document.downloaded_data_)
    elif document.mime_type == 'application/x-tgsticker':
        data, width, height, mime_type = _convert_animation(document.downloaded_data_)
    else:
        return
    return Sticker(data, alt, width, height, document.size, mime_type)


class TelegramExporter:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, secrets_filename: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.secrets_filename = secrets_filename

        self.client = TelegramClient(self.secrets_filename, self.api_id, self.api_hash, system_version="4.16.30-vxStickerBridge")

    async def connect(self):
        await self.client.start(bot_token=self.bot_token)

    async def close(self):
        await self.client.disconnect()

    async def get_stickerset(self, pack_name: str) -> list[Sticker]:
        logging.getLogger('telethon').setLevel(logging.WARNING)

        result: List[Sticker] = list()

        try:
            sticker_set = await self.client(GetStickerSetRequest(InputStickerSetShortName(short_name=pack_name), hash=0))
        except StickersetInvalidError:
            return result  # return empty on fail

        downloaded_documents = []

        with tqdm(total=len(sticker_set.documents)) as tqdm_object:
            for document_data in sticker_set.documents:
                document_data.downloaded_data_ = await self.client.download_media(document_data, file=bytes)
                downloaded_documents.append(document_data)
                tqdm_object.update(1)

        logging.info(f"Processing downloaded stickers...")
        pool = Pool()
        # result = pool.map(_process_sticker, downloaded_documents)
        result = list(tqdm(pool.imap(_process_sticker, downloaded_documents), total=len(downloaded_documents)))

        return result
