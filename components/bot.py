import json
from urllib.parse import quote
import asyncio
import datetime
import random
import discord
import os.path


from components.minigolf import utc_to_local, get_score_message


local_tz = "Europe/Helsinki"

def init_bot(cfg, gsheets, grequests, loc_tz):
    global local_tz
    local_tz = loc_tz
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True
    intents.messages = True
    client = Bot(intents=intents)
    client.configure(cfg, gsheets, grequests)
    return client


class Bot(discord.Client):
    config = None
    current_thread = None
    game_channel = None
    pending_channel_ids = {}
    channels = {}
    api_conf = None
    super_admin = []
    played = []
    gsheets = None
    current_hole = -1
    is_ready = False
    request_ass = None
    nicks = {}

    role_messages = {}

    def configure(self, config, gsheets, grequests):
        self.gsheets = gsheets
        self.request_ass = grequests
        admins = config['BOT']['SUPER_ADMIN'].split(",")
        if 'API' in config:
            self.api_conf = config['API']
        for a in range(len(admins)):
            self.super_admin.append(int(admins[a]))
        self.pending_channel_ids[config["BOT"]['GAMING_CHANNEL_ID']] = "game_channel"
        self.load_nicks()


    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        await self.get_channel_ids()
        await self.load_role_messages()
        self.is_ready = True

    async def get_channel_ids(self):
        channels = self.get_all_channels()
        for channel in channels:
            if str(channel.id) in self.pending_channel_ids:
                pending_channel = self.pending_channel_ids[str(channel.id)]
                if pending_channel == "game_channel":
                    self.game_channel = channel
                    print("got game channel from conf!")
            if channel.type == discord.ChannelType.text:
                self.channels[channel.name] = channel


    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        if message.content.lower() == "haloo":
            if random.random() > 0.5:
                await message.reply("haloo?")
            else:
                await message.reply("haloo!")
        if message.content.lower() == "haloo?":
            await message.reply("haloo!")
        if message.content.lower() == "haloo!":
            await message.reply("haloo?")

        if message.content.startswith("!"):
            await self.handle_command(message)

        if self.current_thread and message.channel.id == self.current_thread.id:
            await self.check_if_score_message(message)

    async def on_raw_reaction_add(self, reaction):
        msgs = await self.get_role_message_or_none(reaction.message_id)
        if msgs:
            emoji = str(reaction.emoji)
            for rm in msgs:
                if rm["emoji"] == emoji:
                    msg = rm["msg"]
                    user = msg.guild.get_member(reaction.user_id)
                    role = msg.guild.get_role(rm["role"])
                    if user and role:
                        if not user.get_role(role.id):
                            await user.add_roles(role)

    async def on_raw_reaction_remove(self, reaction):
        msgs = await self.get_role_message_or_none(reaction.message_id)
        if msgs:
            emoji = str(reaction.emoji)
            for rm in msgs:
                if rm["emoji"] == emoji:
                    msg = rm["msg"]
                    user = msg.guild.get_member(reaction.user_id)
                    role = msg.guild.get_role(rm["role"])
                    if user and role:
                        if user.get_role(role.id):
                            await user.remove_roles(role)


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

    async def check_bot_admin(self, user, guild):
        ok = await self.check_for_role(user, guild, "luu_admin")
        return ok

    async def check_bot_mod(self, user, guild):
        ok = await self.check_for_role(user, guild, "luu_mod")
        return ok


    async def get_role_with_str(self, guild, role_s):
        for role in guild.roles:
            if role.name == role_s:
                return role
        return None

    async def check_for_role(self, user, guild, role_s):
        role = await self.get_role_with_str(guild, role_s)
        if role:
            if user.get_role(role.id):
                return True
            return False
        print("No such role in guild: ", role_s)
        return False

    async def get_role_from_mention(self, guild, mention):
        for role in guild.roles:
            if role.mention == mention:
                return role
        return None

    async def get_message_from_channel_with_id(self, c_id, m_id):
        channel = self.get_channel(c_id)
        try:
            msg = await channel.fetch_message(m_id)
            return msg, False
        except discord.NotFound:
            return None, True
        except discord.Forbidden, discord.HTTPException:
            return None, False

    async def handle_command(self, message):
        args = message.content.split(" ")
        cmd = args[0][1:].lower()
        if cmd == "roolita":
            if await self.check_bot_mod(message.author, message.guild):
                if message.reference and message.reference.message_id and len(args) > 2:
                    role = await self.get_role_from_mention(message.guild, args[1])
                    emoji = args[2].strip()
                    if not role:
                        role = await self.get_role_from_mention(message.guild, args[2])
                        emoji = args[1].strip()
                    if not role:
                        await message.reply(f'Ei oo tommosta roolii..')
                    msg, e = await self.get_message_from_channel_with_id(message.channel.id, message.reference.message_id)
                    if not msg:
                        await message.reply(f'Done goofed..')
                        return False
                    await msg.add_reaction(emoji)
                    await self.add_role_checker_entry(role.id, emoji, msg.id, msg.channel.id)
                    await self.add_role_message_cache(msg, role.id, emoji, msg.channel.id)
                    await message.add_reaction("✅")
                    await asyncio.sleep(5)
                    await message.delete()
                    return True
                elif not message.reference:
                    await message.reply(f'Mikä viesti? hä?')
            else:
                await message.reply(f'Sori, sä et määrää täällä.')

        if cmd == "epäroolita":
            if await self.check_bot_mod(message.author, message.guild):
                if message.reference and message.reference.message_id and len(args) > 2:
                    role = await self.get_role_from_mention(message.guild, args[1])
                    emoji = args[2].strip()
                    if not role:
                        role = await self.get_role_from_mention(message.guild, args[2])
                        emoji = args[1].strip()
                    if not role:
                        await message.reply(f'Ei oo tommosta roolii..')
                    msg, e = await self.get_message_from_channel_with_id(message.channel.id, message.reference.message_id)
                    if not msg:
                        await message.reply(f'Done goofed..')
                        return False
                    delet = False
                    if len(args) > 3 and args[3] == "poista":
                        delet = True
                    await self.remove_role_message(delet, msg, role.id, emoji, msg.channel.id)
                    await message.add_reaction("✅")
                    await asyncio.sleep(5)
                    await message.delete()
                    return True
                elif not message.reference:
                    await message.reply(f'Mikä viesti? hä?')
            else:
                await message.reply(f'Sori, sä et määrää täällä.')

        if cmd == "haloo" or cmd == "haloo!":
            if len(args) > 2:
                if args[1] == "puhelimessa":
                    await self.save_nick(message.author.id, args[2])
                    await message.reply(f'Haloo {args[2]}! Luurissa luuranki.')
                if args[1] == "missä" and (args[2] == "reikä?" or args[2] == "reikä"):
                    hole_arg = -1
                    if len(args) > 3 and args[3].is_digit():
                        hole_arg = int(args[3])
                    ttc = self.gsheets.fetchfromsheets("Daily Minigolf Challenge", "Outputs", "ThreadTitleContent")
                    if len(ttc) == 2:
                        title = ttc[0][0]
                        content = ttc[1][0]
                        hole = title.split(" ")[0]
                        if len(hole) > 1 and hole[1:].is_digit():
                            hole = int(hole[1:])
                            if hole_arg > 0:
                                if hole_arg == hole and self.current_hole != hole:
                                    await message.reply(f'Mää luulin että pitäs olla reikä {self.current_hole} mut sanoit että ois {hole_arg} ja sheetistä löyty reikä {hole}... Korjaan tilanteen...')
                                    self.current_hole = hole
                                elif hole_arg == self.current_hole and hole != hole_arg:
                                    await message.reply(f'Sheetistä tullee väärää reikää :(')
                            elif self.current_hole != hole:
                                await message.reply(f'No tota.. Sheetistä tulee reikä #{hole} ja mun mielestä pitäs olla #{self.current_hole}')
                            if self.current_hole == hole and (hole_arg == -1 or hole_arg == hole):
                                success, created = await self.make_new_thread(title, content)
                                if success:
                                    if not created:
                                        await message.reply(f'No eiks se oo tää: {self.current_thread.jump_url} ?')
                                    else:
                                        await message.reply(f'💀')


        if cmd == "pelikanava":
            if message.author.id in self.super_admin:
                self.game_channel = message.channel
                await message.add_reaction("☑️")
            else:
                await message.reply("Elä laita tämmöstä. Pyyä slottii laittaa.")

        if cmd == "ilmoitustaulu":
            if len(args) > 2 and (args[1].lower() == "lisää" or args[1].lower() == "poista"):
                txt_id = args[2]
                if txt_id.startswith("-"):
                    await message.reply("Unohditko lisätä ID:n?")
                    return True
                if args[1] == "lisää":
                    adding = None
                    title = []
                    content = []
                    for arg in args[3:]:
                        if arg.lower() == "-o":
                            adding = "o"
                        elif arg.lower() == "-s":
                            adding = "s"
                        else:
                            if adding == "o":
                                title.append(arg)
                            elif adding == "s":
                                content.append(arg)
                    if len(content) > 0:
                        response = await self.post_on_api("/edit-content/"+txt_id,
                                                          {"box": "bulletin_board", "header": " ".join(title), "text": " ".join(content), "author": message.author.display_name})
                        if response["success"]:
                            await message.reply("Postasin!")
                        else:
                            await message.reply("Ei toimi... " + response["content"])
                        return True
                    await message.reply("Lissää ny ees jottai sisältöö. -s aaasdsad")
                    return False
                if args[1] == "poista":
                    response = await self.delete_on_api("/edit-content/"+txt_id, {})
                    if response["success"]:
                        await message.reply("Poistettu!")
                    else:
                        await message.reply("Ei toimi... " + response["content"])
                    return True




            await message.reply('Käyttö: \n!ilmoitustaulu lisää TXT_ID (-o TEKSTIN OTSIKKO) -s TEKSTIN SISÄLTÖ\n!ilmoitustaulu pista TXT_ID')
        if cmd == "perttijumis":
            offset = 0
            if len(args) > 1:
                offset_arg = args[1]
                if len(args) > 2:
                    if args[2] == "h" or args[2] == "d" or args[2] == "t" or args[2] == "p" or args[2] == "pv":
                        offset_arg += args[2]
                if is_float(offset_arg):
                    offset = float(offset_arg)*24
                if offset_arg.endswith("t") or offset_arg.endswith("h"):
                    if is_float(offset_arg[:-1]):
                        offset = float(offset_arg[:-1])
                if offset_arg.endswith("d") or offset_arg.endswith("p") or offset_arg.endswith("pv"):
                    if is_float(offset_arg[:-1]):
                        offset = float(offset_arg[:-1])*24
            stuck_time = datetime.datetime.now() - datetime.timedelta(hours=offset)
            response = await self.patch_on_api("/edit-keyvalue/perttiStuck", {"value": str(stuck_time), "author": str(message.author.display_name)})
            if response["success"]:
                await message.reply("Yritin päivittää... (" + str(stuck_time) + ")")
            else:
                await message.reply("Ei toimi... " + response["content"])
            return True
        if cmd == "kuva":
            if len(args) > 1:
                if args[1] == "lisää":
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
                    if not img_url:
                        await message.reply("Kilikoli. En löytäny tuosta mittää lisättävää :(")
                        return True
                    img_url = quote(img_url, safe='/:?&=')
                    response = await self.post_on_api("/edit-image", {"url": img_url, "author": message.author.display_name})
                    if response["success"]:
                        await message.reply("Kuva lisätty.. ehkä.")
                    else:
                        await message.reply("Ei toimi... " + response["content"])
                    return True

                elif args[1] == "poista":
                    if len(args) > 2 and args[2].isdigit():
                        response = await self.delete_on_api("/edit-image/" + args[2], {})
                        if response["success"]:
                            await message.reply("Kuva poistettu... ehkä.")
                        else:
                            await message.reply("Ei toimi... " + response["content"])
                        return True
                await message.reply("Kili koli, en tajuu...")
                return True
            await message.reply("pistä perään urli tai 'poista <id>'")
        return False

    async def save_nick(self, author, nick):
        self.nicks[author] = nick
        with open('data/nicknames.json', 'w+') as json_data:
            json.dump(self.nicks, json_data)

    async def get_nick(self, author):
        if author.id in self.nicks:
            return self.nicks[author.id]
        return author.display_name

    def load_nicks(self):
        if os.path.isfile('data/nicknames.json'):
            with open('data/nicknames.json', 'r+') as json_data:
                self.nicks = json.load(json_data)
        else:
            with open('data/nicknames.json', 'w+') as json_data:
                json.dump({}, json_data)


    async def can_api(self):
        return self.api_conf and 'API_URL' in self.api_conf

    async def can_auth(self):
        return await self.can_api() and 'USER' in self.api_conf and 'KEY' in self.api_conf

    async def get_on_api(self, path):
        if await self.can_api():
            # Create a set of unsent Requests
            urls = [self.api_conf['API_URL'] + path]
            requests = (self.request_ass.get(url) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api conf"}

    async def handle_request(self, requests):
        responses = self.request_ass.map(requests)
        for response in responses:
            if response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return {"success": True, "content": data}
                    except json.JSONDecodeError:
                        return {"success": False, "content": response.text}
                else:
                    try:
                        data = response.json()
                        content = ["ERROR!", str(response.status_code)]
                        if "error" in data:
                            content.append(data["error"])
                        if "message" in data:
                            content.append(data["message"])

                        return {"success": True, "content": " ".join(content)}
                    except json.JSONDecodeError:
                        return {"success": False, "content": "ERROR! " + str(response.status_code) + " " + response.text}


        return {"success": False, "content": "Request failed :("}

    async def post_on_api(self, path, data):
        if await self.can_auth():
            urls = [self.api_conf['API_URL'] + path]
            requests = (self.request_ass.post(url, json=data, auth=(self.api_conf['USER'], self.api_conf['KEY'])) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api keys"}

    async def delete_on_api(self, path, data):
        if await self.can_auth():
            urls = [self.api_conf['API_URL'] + path]
            requests = (self.request_ass.delete(url, json=data, auth=(self.api_conf['USER'], self.api_conf['KEY'])) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api keys"}


    async def patch_on_api(self, path, data):
        if await self.can_auth():
            urls = [self.api_conf['API_URL'] + path]
            requests = (self.request_ass.patch(url, json=data, auth=(self.api_conf['USER'], self.api_conf['KEY'])) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api keys"}


    async def check_if_score_message(self, message):
        score_msg = await get_score_message(message.content)
        if score_msg:
            await message.add_reaction("👏")
            await message.add_reaction("🤔")
            sender = await self.get_nick(message.author)
            created = utc_to_local(message.created_at)
            timestamp = "[" + str(created.hour).zfill(2) + ":" + str(created.minute).zfill(2) + "]"
            score_msg = timestamp + sender + ": " + score_msg + " 🤖 Added by luuranki"
            res = self.gsheets.add_new_minigolf_line(score_msg, self.current_hole, sender)
            await message.remove_reaction("🤔", self.user)
            if res:
                await message.add_reaction("✅")
            else:
                await message.add_reaction("❎")
                await asyncio.sleep(5)
                await message.add_reaction("💀")

    async def check_message_history(self):
        async for msg in self.current_thread.history(limit=200, oldest_first=True):
            checked = False
            for r in msg.reactions:
                if r.me or (isinstance(r.emoji, str) and (r.emoji == "❎" or r.emoji == "✅")):
                    checked = True
                    break
            if not checked:
                await self.check_if_score_message(msg)

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
                msg, e = await self.get_message_from_channel_with_id(rm["channel"], rm["msg"])
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

    async def make_new_thread(self, title, content):
        self.played = []
        if self.game_channel:
            threads = self.game_channel.threads
            for t in range(len(threads)):
                thread = threads[t]
                if thread.name == title:
                    self.current_thread = thread
                    await self.check_message_history()
                    return True, False
            self.current_thread = await self.game_channel.create_thread(name=title, type=discord.ChannelType.public_thread)
            mentions_fix = await self.make_mentions(content)
            await self.current_thread.send(mentions_fix)
            return True, True
        return False, False

    async def make_mentions(self, content:str):
        roles = self.game_channel.guild.roles
        for role in roles:
            if role.mentionable:
                n = "@" + role.name
                content = content.replace(n, role.mention)
        return content

def is_float(element) -> bool:
    #If you expect None to be passed:
    if element is None:
        return False
    try:
        float(element)
        return True
    except ValueError:
        return False

