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


class TelegramExporter:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, secrets_filename: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.secrets_filename = secrets_filename

        self.client = TelegramClient(self.secrets_filename, self.api_id, self.api_hash)

    async def connect(self):
        await self.client.start(bot_token=self.bot_token)

    async def get_stickerset(self, pack_name: str) -> list[Sticker]:
        result: List[Sticker] = list()

        try:
            sticker_set = await self.client(GetStickerSetRequest(InputStickerSetShortName(short_name=pack_name), hash=0))
        except StickersetInvalidError:
            return result
        for sticker_document in sticker_set.documents:
            alt = sticker_document.attributes[1].alt
            raw_data = await self.client.download_media(sticker_document, file=bytes)
            if sticker_document.mime_type == 'image/webp':
                data, width, height = _convert_image(raw_data)
                result.append(Sticker(data, alt, 'image/png'))
            if sticker_document.mime_type == 'application/x-tgsticker':
                data = _convert_animation(raw_data)
                result.append(Sticker(data, alt, 'image/webp'))

        return result
