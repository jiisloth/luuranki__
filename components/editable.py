from discord import Message


class Editable:
    channel = None
    required_role = None

    def __init__(self, bot):
        self.bot = bot

    async def setup(self, channel, required_role=None):
        self.required_role = required_role
        if self.channel != channel:
            self.channel = channel
            await self.reset_content()

    async def check_message(self, message, channel_id, check_role=False):
        if self.channel:
            if self.channel.id == channel_id:
                if check_role and self.required_role:
                    if not message:
                        return False
                    ok = await self.bot.check_for_role(message.author, message.guild, self.required_role)
                    if not ok:
                        await message.add_reaction("❌")
                        return False
                return True
        return False

    async def reset_content(self):
        return False

    async def on_new_message(self, message: Message, content_override=""):
        if await self.check_message(message, message.channel.id, True):
            await self.add(message, content_override)

    async def on_message_delete(self, raw_del_event):
        if await self.check_message(None, raw_del_event.channel_id):
            await self.delete(raw_del_event.message_id)

    async def on_message_edited(self, message: Message, content_override=""):
        if await self.check_message(message, message.channel.id, True):
            await self.modify(message)


    async def add(self, message, content_override=""):
        return True

    async def delete(self, message):
        return True

    async def modify(self, message, content_override=""):
        return True
