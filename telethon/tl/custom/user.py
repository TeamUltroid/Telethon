import traceback
from .. import types, functions
from ... import utils

class USER(types.User):
    def __init__(self, id:int=None, *args, **kwargs):
        self._client = None
        self._id = id

        for kwg in kwargs:
            setattr(self, kwg, kwargs[kwg])

        _is_ult = any(("core/__main__" in file.filename or 
                       'core\\__main__' in file.filename) for file in traceback.extract_stack())
        if _is_ult and self.is_self and self.phone:
            self.phone = "**********"
        if self.restriction_reason is None:
            self.restriction_reason = []
        self._fulluser = None


    def _set_client(self, client):
        self._client = client

    @property
    def id(self):
        return self._id

    @property
    def mention(self):
        return f"[{utils.get_display_name(self)}](tg://user?id={self.id})"

    @property
    def full_user(self):
        return self._full_user

    async def comman_chats(self, max_id=0, limit=0):
        if self._client:
            chat = await self._client(functions.messages.GetCommonChatsRequest(self.id, max_id=max_id, limit=limit))
            if not isinstance(chat, types.messages.ChatsSlice):
                chat.count = len(chat.chats)
            return chat

    async def get_fulluser(self):
        if self._client:
            full_user = await self._client(functions.users.GetFullUserRequest(self.id))
            self._full_user = full_user.full_user
            return full_user

    async def block(self):
        if self._client:
            return await self._client(functions.contacts.BlockRequest(self.id))

    async def unblock(self):
        if self._client:
            return await self._client(functions.contacts.UnblockRequest(self.id))

    async def send(self, *args, **kwargs):
        if self._client:
            return await self._client.send_message(self.id, *args, **kwargs)

    async def get_photos(self, *args, **kwargs):
        if self._client:
            return await self._client.get_profile_photos(self.id, *args, **kwargs)