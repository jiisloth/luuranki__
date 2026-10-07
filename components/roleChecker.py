import json
import os


class RoleChecker:
    role_messages = {}

    def __init__(self, bot):
        self.bot = bot

    async def on_raw_reaction_add(self, reaction):
        await self.handle_reaction(reaction, True)

    async def on_raw_reaction_remove(self, reaction):
        await self.handle_reaction(reaction, False)

    async def handle_reaction(self, reaction, add):
        msgs = await self.get_role_message_or_none(reaction.message_id)
        if msgs:
            emoji = str(reaction.emoji)
            for rm in msgs:
                if rm["emoji"] == emoji:
                    msg = rm["msg"]
                    user = msg.guild.get_member(reaction.user_id)
                    role = msg.guild.get_role(rm["role"])
                    if user and role:
                        if add and not user.get_role(role.id):
                            await user.add_roles(role)
                        if not add and user.get_role(role.id):
                            await user.remove_roles(role)


    async def load_role_messages(self):
        if not os.path.isfile('data/rolemessage.json'):
            with open('data/rolemessage.json', "w+") as json_data:
                json.dump([], json_data)
        with open('data/rolemessage.json', "r+") as json_data:
            rolemsgs = json.load(json_data)
        valid = []
        changes = False
        for rm in rolemsgs:
            ok, delet = await self.check_role_message(rm)
            if not delet:
                valid.append(rm)
            else:
                changes = True
        if changes:
            with open('data/rolemessage.json', "w+") as json_data:
                json.dump(valid, json_data)

    async def remove_role_checker_entry(self, role, emoji, msg, channel):
        with open('data/rolemessage.json', "r+") as json_data:
            rolemsgs = json.load(json_data)
        valid = []
        changes = False
        for rm in rolemsgs:
            if not (rm["role"] == role and rm["emoji"] == emoji and rm["msg"] == msg and rm["channel"] == channel):
                valid.append(rm)
                changes = True
        if changes:
            with open('data/rolemessage.json', "w+") as json_data:
                json.dump(valid, json_data)


    async def add_role_checker_entry(self, role, emoji, msg, channel):
        with open('data/rolemessage.json', "r+") as json_data:
            rolemsgs = json.load(json_data)
        found = False
        for rm in rolemsgs:
            if rm["role"] == role and rm["emoji"] == emoji and rm["msg"] == msg and rm["channel"] == channel:
                found = True
                break
        if not found:
            rolemsgs.append({"msg": msg, "role": role, "emoji": emoji, "channel": channel})
            with open('data/rolemessage.json', "w+") as json_data:
                json.dump(rolemsgs, json_data)

    async def check_role_message(self, rm):
        if "msg" in rm and "role" in rm and "channel" in rm and "emoji" in rm:
            msg = None
            msgs = await self.get_role_message_or_none(rm["msg"])
            if msgs:
                for rmc in msgs:
                    if rmc["emoji"] == rm["emoji"] and rmc["role"] == rm["role"] and rmc["channel_id"] == rm["channel"]:
                        msg = rmc["msg"]
                        break
            if not msg:
                msg, e = await self.bot.get_message_from_channel_with_id(rm["channel"], rm["msg"])
                if msg:
                    await self.add_role_message_cache(msg, rm["role"], rm["emoji"], rm["channel"])
                else:
                    return False, e
            if msg:
                user_ids = []
                role = msg.guild.get_role(rm["role"])
                if not role:
                    await self.remove_role_message_from_cache(rm["msg"], rm["role"], rm["emoji"], rm["channel"])
                    return False, True
                for reaction in msg.reactions:
                    emoji = None
                    if isinstance(reaction.emoji, str):
                        emoji = reaction.emoji
                    else:
                        emoji = str(reaction.emoji)
                    if rm["emoji"] == emoji:
                        async for user in reaction.users():
                            user_ids.append(user.id)
                            if not user.get_role(role.id):
                                await user.add_roles(role)
                for mem in role.members:
                    if mem.id not in user_ids:
                        await mem.remove_roles(role)

                return True, False
            return False, True
        return False, True


    async def get_role_message_or_none(self, m_id):
        if m_id in self.role_messages:
            return self.role_messages[m_id]
        return None

    async def add_role_message_cache(self, msg, role, emoji, channel_id):
        if not msg.id in self.role_messages:
            self.role_messages[msg.id] = []
        self.role_messages[msg.id].append({
            "msg": msg,
            "role": role,
            "emoji": emoji,
            "channel_id": channel_id
        })

    async def remove_role_message(self, remove_role, msg, role_s, emoji, channel_id):
        found = await self.remove_role_message_from_cache(msg.id, role_s, emoji, channel_id)
        await self.remove_role_checker_entry(role_s, emoji, msg.id, channel_id)
        if found and remove_role:
            role = msg.guild.get_role(role_s)
            if role:
                for mem in role.members:
                    await mem.remove_roles(role)

    async def remove_role_message_from_cache(self, m_id, role_s, emoji, channel_id):
        if m_id in self.role_messages:
            for rm in self.role_messages[m_id]:
                if rm["channel_id"] == channel_id and rm["emoji"] == emoji and rm["role"] == role_s:
                    self.role_messages[m_id].remove(rm)
                    return True
        return False

