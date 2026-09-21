import json
from urllib.parse import quote
import asyncio
import datetime
import random
import discord


from components.minigolf import utc_to_local, get_score_message
from components.roleChecker import add_role_checker_entry


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


    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        await self.get_channel_ids()
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

    async def handle_command(self, message):
        args = message.content.split(" ")
        cmd = args[0][1:].lower()
        if cmd == "roolita":
            if message.author.id in self.super_admin:
                if message.reference and len(args) > 2:
                    role = args[1]
                    emoji = args[2]
                    msg = message.reference
                    await add_role_checker_entry(role, emoji, msg.id, msg.channel.id)
                    self.role_messages[msg.id] = msg
        if cmd == "haloo":
            if len(args) > 2:
                if args[1] == "missä" and (args[2] == "reikä?" or args[2] == "reikä"):
                    hole_arg = -1
                    if len(args) > 3 and args[3].is_digit():
                        hole_arg = int(args[3])
                    ttc = self.gsheets.fetchfromsheets("Daily Minigolf Challenge", "DiscordThreadCopyPasta", "ThreadTitleContent")
                    if len(ttc) == 2:
                        title = ttc[0][0]
                        content = ttc[1][0]
                        hole = title.split(" ")[0]
                        if len(hole) > 1 and hole[1:].is_digit():
                            hole = int(hole[1:])
                            if hole_arg > 0:
                                if hole_arg == hole and self.current_hole != hole:
                                    message.reply(f'Mää luulin että pitäs olla reikä {self.current_hole} mut sanoit että ois {hole_arg} ja sheetistä löyty reikä {hole}... Korjaan tilanteen...')
                                    self.current_hole = hole
                                elif hole_arg == self.current_hole and hole != hole_arg:
                                    message.reply(f'Sheetistä tullee väärää reikää :(')
                            elif self.current_hole != hole:
                                message.reply(f'No tota.. Sheetistä tulee reikä #{hole} ja mun mielestä pitäs olla #{self.current_hole}')
                            if self.current_hole == hole and (hole_arg == -1 or hole_arg == hole):
                                success, created = await self.make_new_thread(title, content)
                                if success:
                                    if not created:
                                        message.reply(f'No eiks se oo tää: {self.current_thread.jump_url} ?')
                                    else:
                                        message.reply(f'💀')


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
            print("pertti jumis")
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
                if args[1].startswith("https://"):
                    img_url = quote(args[1], safe='/:?&')
                    print(img_url)
                    response = await self.post_on_api("/edit-image", {"url": img_url, "author": message.author.display_name})
                    if response["success"]:
                        await message.reply("Kuva lisätty.. ehkä.")
                    else:
                        await message.reply("Ei toimi... " + response["content"])
                    return True

                elif args[1] == "poista":
                    if len(args) > 2 and args[2].isdigit():
                        response = await self.delete_on_api("/edit-image/" + args[2])
                        if response["success"]:
                            await message.reply("Kuva lisätty.. ehkä.")
                        else:
                            await message.reply("Ei toimi... " + response["content"])
                        return True
                await message.reply("Kili koli, en tajuu...")
                return True
            await message.reply("pistä perään urli tai 'poista <id>'")
        return False

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
            sender = message.author.display_name
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

    async def check_role_message(self, rm):
        if "msg" in rm and "role" in rm and "channel" in rm and "emoji" in rm:
            msg = None
            if rm["msg"] in self.role_messages:
                msg = self.role_messages[rm["msg"]]
            else:
                channel = self.get_channel(rm["channel"])
                try:
                    msg = await channel.fetch_message(rm["msg"])
                except discord.NotFound:
                    return False, True
                except discord.Forbidden, discord.HTTPException:
                    return False, False
                if msg:
                    self.role_messages[msg.id] = msg
            if msg:
                user_ids = []
                role = msg.guild.get_role(rm["role"])
                if not role:
                    del self.role_messages[msg.id]
                    return False, True
                for reaction in msg.reactions:
                    emoji = None
                    if isinstance(reaction.emoji, str):
                        emoji = reaction.emoji
                    else:
                        emoji = reaction.emoji.name
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