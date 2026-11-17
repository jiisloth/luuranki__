from discord import Message

from components.editable import Editable

class Gallery(Editable):
    def get_img_from_message(self, message):

        img_url = None
        for ach in message.attachments:
            if ach.content_type.startswith("image"):
                img_url = ach.url
                break
        if not img_url:
            for emb in message.embeds:
                if emb.image and emb.image.proxy_url:
                    img_url = emb.image.proxy_url
                elif emb.image and emb.image.url:
                    img_url = emb.image.url
                elif emb.thumbnail and emb.thumbnail.proxy_url:
                    img_url = emb.thumbnail.proxy_url
                elif emb.thumbnail and emb.thumbnail.url:
                    img_url = emb.thumbnail.url
                elif emb.type == "image" and emb.url:
                    img_url = emb.url
                if img_url:
                    break
        return img_url

    async def add(self, message:Message):
        img_url = self.get_img_from_message(message)
        if img_url:
            data = {
                "url": img_url,
                "author": message.author.display_name
            }
            response = await self.bot.api.post_req("/edit-image/" + str(message.id), data)
            if response["success"]:
                await message.add_reaction("✔️")
            else:
                await message.add_reaction("✖️")
        else:
            await message.add_reaction("✖️")
        return True

    async def delete(self, message):
        response = await self.bot.api.delete_req("/edit-image/" + str(message.id), {})
        return True

    async def modify(self, message):
        await message.add_reaction("✖️")
        return True
