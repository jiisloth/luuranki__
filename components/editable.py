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

    async def check_message(self, message, check_role=False):
        if self.channel:
            if self.channel.id == message.channel.id:
                if check_role and self.required_role:
                    ok = await self.bot.check_for_role(message.author, message.guild, self.required_role)
                    if not ok:
                        await message.add_reaction("❌")
                        return False
                return True
        return False

    async def reset_content(self):
        return False

    async def on_new_message(self, message: Message):
        if await self.check_message(message, True):
            await self.add(message)

    async def on_message_deleted(self, message: Message):
        if await self.check_message(message):
            await self.delete(message)

    async def on_message_edited(self, message: Message):
        if await self.check_message(message, True):
            await self.modify(message)


    async def add(self, message):
        return True

    async def delete(self, message):
        return True

    async def modify(self, message):
        return True
