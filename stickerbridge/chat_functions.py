import os

import aiofiles.os
import magic
import logging

from nio import AsyncClient, UploadResponse, ErrorResponse, RoomGetStateEventError

from sticker_types import MatrixStickerset


async def send_text_to_room(client: AsyncClient, room_id: str, message: str):
    content = {
        "msgtype": "m.notice",
        "body": message,
    }
    return await client.room_send(
        room_id,
        "m.room.message",
        content,
    )

async def send_text_to_room_as_text(client: AsyncClient, room_id: str, message: str):
    content = {
        "msgtype": "m.text",
        "body": message,
    }
    return await client.room_send(
        room_id,
        "m.room.message",
        content,
    )

async def send_sticker_to_room(client: AsyncClient, room_id: str, content: dict):
    return await client.room_send(
        room_id,
        "m.sticker",
        content,
    )

async def has_permission(client: AsyncClient, room_id: str, permission_type: str):
    """Reimplementation of AsyncClient.has_permission because matrix-nio version always gives an error
    https://github.com/poljar/matrix-nio/issues/324"""
    user_id = client.user
    power_levels = await client.room_get_state_event(room_id, "m.room.power_levels")
    try:
        user_power_level = power_levels.content['users'][user_id]
    except KeyError:
        try:
            user_power_level = power_levels.content['users_default']
        except KeyError:
            return ErrorResponse("Couldn't get user power levels")

    try:
        permission_power_level = power_levels.content[permission_type]
    except KeyError:
        return ErrorResponse(f"permission_type {permission_type} unknown")

    return user_power_level >= permission_power_level


async def is_stickerpack_existing(client: AsyncClient, room_id: str, pack_name: str):
    response = (await client.room_get_state_event(room_id, 'im.ponies.room_emotes', pack_name))
    if isinstance(response, RoomGetStateEventError) and response.status_code == 'M_NOT_FOUND':
        return False
    return not response.content == {}


async def get_stickerpack(client: AsyncClient, room_id: str, pack_name: str):
    response = (await client.room_get_state_event(room_id, 'im.ponies.room_emotes', pack_name))
    return response.content


async def upload_stickerpack(client: AsyncClient, room_id: str, stickerset: MatrixStickerset, name):
    return await client.room_put_state(room_id, 'im.ponies.room_emotes', stickerset.json(), state_key=name)

async def update_room_image(client: AsyncClient, room_id: str, image: str):
    return await client.room_put_state(room_id, 'm.room.avatar', {"url": image})

async def update_room_name(client: AsyncClient, room_id: str, name: str):
    return await client.room_put_state(room_id, 'm.room.name', {"name": name})

async def update_room_topic(client: AsyncClient, room_id: str, topic: str):
    return await client.room_put_state(room_id, 'm.room.topic', {"topic": topic})

async def upload_image(client: AsyncClient, image: str):
    mime_type = magic.from_file(image, mime=True)
    file_stat = await aiofiles.os.stat(image)
    async with aiofiles.open(image, "r+b") as f:
        try:
            resp, maybe_keys = await client.upload(
                f,
                content_type=mime_type,
                filename=os.path.basename(image),
                filesize=file_stat.st_size,
            )
        except:
            logging.error(f"Failed to upload image ({image})")
            return ""
    if isinstance(resp, UploadResponse):
        logging.debug(f"Image {image} was uploaded successfully to server.")
        return resp.content_uri
    else:
        logging.error(f"Failed to upload image ({image}). Failure response: {resp}")
        return ""


async def upload_avatar(client: AsyncClient, image: str):
    avatar_mxc = await upload_image(client, image)
    if avatar_mxc:
        await client.set_avatar(avatar_mxc)
