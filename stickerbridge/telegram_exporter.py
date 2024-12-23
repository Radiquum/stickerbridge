from multiprocessing import Pool
from typing import List

from lottie.importers import importers
from lottie.exporters import exporters
from telethon import TelegramClient
from telethon.errors import StickersetInvalidError
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName

from io import BytesIO
from PIL import Image

from sticker_types import Sticker


def _convert_image(data: bytes) -> (bytes, int, int):
    image: Image.Image = Image.open(BytesIO(data)).convert("RGBA")
    new_file = BytesIO()
    image.save(new_file, "webp")
    w, h = image.size
    if w > 256 or h > 256:
        if w > h:
            h = int(h / (w / 256))
            w = 256
        else:
            w = int(w / (h / 256))
            h = 256
    return new_file.getvalue(), w, h


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
    return out.getvalue()


def _process_sticker(document) -> Sticker:
    alt = document.attributes[1].alt
    if document.mime_type == 'image/webp':
        data, width, height = _convert_image(document.downloaded_data_)
    if document.mime_type == 'application/x-tgsticker':
        data = _convert_animation(document.downloaded_data_)
    return Sticker(data, alt)


class TelegramExporter:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, secrets_filename: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.secrets_filename = secrets_filename

        self.client = TelegramClient(self.secrets_filename, self.api_id, self.api_hash, system_version="4.16.30-vxStickerBridge")

    async def connect(self):
        await self.client.start(bot_token=self.bot_token)

    async def get_stickerset(self, pack_name: str) -> list[Sticker]:
        result: List[Sticker] = list()

        short_name = pack_name
        if short_name.startswith('http'):
            short_name = pack_name.split("/")[-1]

        try:
            sticker_set = await self.client(GetStickerSetRequest(InputStickerSetShortName(short_name=short_name), hash=0))
        except StickersetInvalidError:
            return result  # return empty on fail

        downloaded_documents = []
        for document_data in sticker_set.documents:
            document_data.downloaded_data_ = await self.client.download_media(document_data, file=bytes)
            downloaded_documents.append(document_data)

        pool = Pool()
        result = pool.map(_process_sticker, downloaded_documents)

        return result
