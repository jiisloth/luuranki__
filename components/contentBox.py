from discord import Message

from components.editable import Editable


class ContentBox(Editable):
    def __init__(self, bot, box="bulletin_board"):
        super().__init__(bot)
        self.box = box


    async def add(self, message:Message):
        data = {
            "box": self.box,
            "text": message.content,
            "author": message.author.display_name
        }
        response = await self.bot.api.post_req("/edit-content/" + str(message.id), data)
        if response["success"]:
            await message.add_reaction("✔️")
        else:
            await message.add_reaction("✖️")
        return True

    async def delete(self, message):
        response = await self.bot.api.delete_req("/edit-content/" + str(message.id), {})
        return True

    async def modify(self, message):
        message.remove_reaction("✔️", self.bot.user)
        message.remove_reaction("✖️", self.bot.user)
        data = {
            "box": self.box,
            "text": message.content,
            "author": message.author.display_name
        }
        response = await self.bot.api.post_req("/edit-content/" + str(message.id), data)
        if response["success"]:
            await message.add_reaction("✔️")
        else:
            await message.add_reaction("✖️")

        return True
