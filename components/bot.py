import json
from urllib.parse import quote
import asyncio
import datetime
import random
import discord
import os.path
from typing import Union, Callable, Coroutine, Any, Sequence
from discord import TextChannel, Thread, Message, Role

from components.minigolf import Minigolf, MinigolfSheet
from components.roleChecker import RoleChecker
from components.verbosity import v_print


def init_bot(cfg, grequests):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True
    intents.messages = True
    client = Bot(intents=intents)
    client.configure(cfg, grequests)
    return client

def sheet_config(key):
    with open('sheet_config.json', 'r+') as json_data:
        conf = json.load(json_data)
    if key in conf:
        return conf[key]
    return None


class Bot(discord.Client):
    config = None
    game_channel = None
    pending_channel_ids = {}
    channels = {}
    api: Api
    super_admin = []
    played = []
    current_hole = -1
    is_ready = False
    nicks = {}
    minigolf:Union[Minigolf, None] = None
    roleChecker:RoleChecker

    def configure(self, config, grequests):
        self.roleChecker = RoleChecker(self)
        admins = config['BOT']['SUPER_ADMIN'].split(",")
        if 'API' in config:
            self.api = Api(grequests, config['API'])
        else:
            self.api = Api(grequests, None)
        for a in range(len(admins)):
            self.super_admin.append(int(admins[a]))
        self.pending_channel_ids[config["BOT"]['GAMING_CHANNEL_ID']] = "game_channel"
        self.load_nicks()
        v_print(1, "Bot configured")


    async def on_ready(self):
        v_print(0, f'Logged on as {self.user}!')
        await self.get_channel_ids()
        await self.roleChecker.load_role_messages()
        await self.restart_tasks()
        self.is_ready = True
        v_print(0, "Ready to go")

    async def get_channel_ids(self):
        channels = self.get_all_channels()
        for channel in channels:
            if str(channel.id) in self.pending_channel_ids:
                pending_channel = self.pending_channel_ids[str(channel.id)]
                if pending_channel == "game_channel":
                    self.game_channel = channel
                    v_print(1, "got game channel from conf!")
                if pending_channel == "bulletin_board":
                    self.game_channel = channel

            if channel.type == discord.ChannelType.text:
                self.channels[channel.name] = channel


    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        v_print(4, message.content)
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

        if self.minigolf and message.channel.id == self.minigolf.game_thread.id:
            await self.minigolf.check_if_score_message(message)

    async def on_raw_reaction_add(self, reaction):
        await self.roleChecker.on_raw_reaction_add(reaction)

    async def on_raw_reaction_remove(self, reaction):
        await self.roleChecker.on_raw_reaction_remove(reaction)


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
        v_print(1, "No such role in guild: ", role_s)
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

    async def handle_command(self, message:Message):
        args = message.content.split(" ")
        cmd = args[0][1:].lower()
        if cmd == "roolita":
            return await self.cmd_set_roles(args, message)
        if cmd == "epäroolita":
            return await self.cmd_unset_roles(args, message)
        if cmd == "haloo" or cmd == "haloo!":
            return await self.cmd_haloo(args, message)
        if cmd == "pelikanava":
            return await self.cmd_game_channel(args, message)
        if cmd == "ilmoitustaulu":
            return await self.cmd_bulletin_board(args, message)
        if cmd == "perttijumis":
            return await self.cmd_pertti_stuck(args, message)
        if cmd == "kuva":
            return await self.cmd_image(args, message)
        return False


    async def cmd_set_roles(self, args, message:Message):
        if await self.check_bot_mod(message.author, message.guild):
            if message.reference and message.reference.message_id and len(args) > 2:
                msg, role, emoji = await self.parse_msg_role_emoji(message, args)
                if not msg or not role:
                    return False
                await msg.add_reaction(emoji)
                await self.roleChecker.add_role_checker_entry(role.id, emoji, msg.id, msg.channel.id)
                await self.roleChecker.add_role_message_cache(msg, role.id, emoji, msg.channel.id)
                await message.add_reaction("✅")
                await asyncio.sleep(5)
                await message.delete()
                return True
            elif not message.reference:
                await message.reply(f'Mikä viesti? hä?')
        else:
            await message.reply(f'Sori, sä et määrää täällä.')
        return False

    async def cmd_unset_roles(self, args, message:Message):
        if await self.check_bot_mod(message.author, message.guild):
            if message.reference and message.reference.message_id and len(args) > 2:
                msg, role, emoji = await self.parse_msg_role_emoji(message, args)
                if not msg or not role:
                    return False
                delet = False
                if len(args) > 3 and args[3] == "poista":
                    delet = True
                await self.roleChecker.remove_role_message(delet, msg, role.id, emoji, msg.channel.id)
                await message.add_reaction("✅")
                await asyncio.sleep(5)
                await message.delete()
                return True
            elif not message.reference:
                await message.reply(f'Mikä viesti? hä?')
        else:
            await message.reply(f'Sori, sä et määrää täällä.')
        return False

    async def parse_msg_role_emoji(self, message, args):
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
        return msg, role, emoji


    async def cmd_haloo(self, args, message:Message):
        if len(args) > 2:
            if args[1] == "puhelimessa":
                await self.save_nick(message.author.id, args[2])
                await message.reply(f'Haloo {args[2]}! Luurissa luuranki.')
            if args[1] == "missä" and (args[2] == "reikä?" or args[2] == "reikä"):

                if self.minigolf:
                    hole_arg = -1
                    if len(args) > 3 and args[3].is_digit():
                        hole_arg = int(args[3])
                    result, reply = await self.minigolf.check_hole_post(hole_arg)
                    if reply:
                        await message.reply(reply)
                    return result
                await message.reply(f'Ei oo peli ees päällä. kai ehkä.')
                return False
            return True
        return False

    async def cmd_game_channel(self, args, message: Message):
        if message.author.id in self.super_admin:
            self.game_channel = message.channel
            if self.minigolf:
                self.minigolf.game_channel = self.game_channel
            await message.add_reaction("☑️")
            return True
        else:
            await message.reply("Elä laita tämmöstä. Pyyä slottii laittaa.")
        return False

    async def cmd_bulletin_board(self, args, message:Message):
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
                    response = await self.api.post_req("/edit-content/"+txt_id,
                                                      {"box": "bulletin_board", "header": " ".join(title), "text": " ".join(content), "author": message.author.display_name})
                    if response["success"]:
                        await message.reply("Postasin!")
                    else:
                        await message.reply("Ei toimi... " + response["content"])
                    return True
                await message.reply("Lissää ny ees jottai sisältöö. -s aaasdsad")
                return False
            if args[1] == "poista":
                response = await self.api.delete_req("/edit-content/"+txt_id, {})
                if response["success"]:
                    await message.reply("Poistettu!")
                else:
                    await message.reply("Ei toimi... " + response["content"])
                return True
        await message.reply('Käyttö: \n!ilmoitustaulu lisää TXT_ID (-o TEKSTIN OTSIKKO) -s TEKSTIN SISÄLTÖ\n!ilmoitustaulu pista TXT_ID')
        return False

    async def cmd_pertti_stuck(self, args, message: Message):
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
        response = await self.api.post_req("/edit-keyvalue/perttiStuck", {"value": str(stuck_time), "author": str(message.author.display_name)})
        if response["success"]:
            await message.reply("Yritin päivittää... (" + str(stuck_time) + ")")
        else:
            await message.reply("Ei toimi... " + response["content"])
        return True

    async def cmd_image(self, args, message: Message):
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
                response = await self.api.post_req("/edit-image", {"url": img_url, "author": message.author.display_name})
                if response["success"]:
                    await message.reply("Kuva lisätty.. ehkä.")
                else:
                    await message.reply("Ei toimi... " + response["content"])
                return True

            elif args[1] == "poista":
                if len(args) > 2 and args[2].isdigit():
                    response = await self.api.delete_req("/edit-image/" + args[2], {})
                    if response["success"]:
                        await message.reply("Kuva poistettu... ehkä.")
                    else:
                        await message.reply("Ei toimi... " + response["content"])
                    return True
            await message.reply("Kili koli, en tajuu...")
            return True
        await message.reply("pistä perään urli tai 'poista <id>'")
        return False

    async def save_nick(self, author_id, nick):
        self.nicks[str(author_id)] = nick
        with open('data/nicknames.json', 'w+') as json_data:
            json.dump(self.nicks, json_data)

    async def get_nick(self, author):
        if str(author.id) in self.nicks:
            return self.nicks[str(author.id)]
        return author.display_name

    def load_nicks(self):
        if os.path.isfile('data/nicknames.json'):
            with open('data/nicknames.json', 'r+') as json_data:
                self.nicks = json.load(json_data)
        else:
            with open('data/nicknames.json', 'w+') as json_data:
                json.dump({}, json_data)



    async def parse_mentions(self, content:str, roles:Sequence[Role]):
        for role in roles:
            if role.mentionable:
                content = content.replace("@" + role.name, role.mention)
        return content

    async def get_thread_with_name(self, channel:TextChannel, thread_name:str, after:Union[None, datetime]=None):
        if channel:
            threads = channel.threads
            for t in range(len(threads)):
                thread = threads[t]
                if after is None or thread.created_at is None or after < thread.created_at:
                    if thread.name == thread_name:
                        return thread
        return None

    async def loop_over_message_history(self, channel:Union[TextChannel, Thread], func:Callable[[Message], Coroutine[Any, Any, dict[str, Any]]], gather=False, limit=200, oldest_first=True):
        results = []
        async for msg in channel.history(limit=limit, oldest_first=oldest_first):
            result = await func(msg)
            if gather and not ("gather" in result and result["gather"]):
                if "return" in result:
                    results.append(result["return"])
            if "halt" in result and result["halt"]:
                if gather:
                    return results
                elif "return" in result:
                    return result["return"]
                return None
        return None

    async def get_or_create_thread(self, channel:TextChannel, title:str, after:Union[None, datetime]=None, public=True, message:str="", parse_mentions=False, invitable=True):
        thread = await self.get_thread_with_name(channel, title, after)
        if thread:
            return thread, False
        thread = await self.create_thread(channel, title, public, message, parse_mentions, invitable)
        return thread, True

    async def create_thread(self, channel:TextChannel, title:str,  public=True, message:str="", parse_mentions=False, invitable=True) -> Thread:
        thread_type = discord.ChannelType.public_thread
        if not public:
            thread_type = discord.ChannelType.private_thread
        thread = await channel.create_thread(name=title, type=thread_type, invitable=True)
        if message != "":
            if parse_mentions:
                message = await self.parse_mentions(message, channel.guild.roles)
            await thread.send(message)
        return thread

    async def invite_to_thread(self, thread: Union[None, Thread], user):
        if thread and thread.invitable:
            await thread.add_user(user)
            return True
        return False

    async def restart_tasks(self):
        await self.restart_running_task("minigolf", self.start_minigolf)

    async def restart_running_task(self, task, func):
        ts = await self.get_task_status(task)
        if ts == "running":
            await func()


    async def start_minigolf(self):
        v_print(1, "Starting minigolf")
        if self.minigolf:
            await self.minigolf.stop()
        minigolf_sheet = MinigolfSheet(sheet_config("minigolf"))
        self.minigolf = Minigolf(self, minigolf_sheet, self.game_channel)
        asyncio.create_task(self.minigolf.start())

    async def save_task_status(self, task, value):
        tasks = {}
        if os.path.isfile('data/tasks.json'):
            with open('data/tasks.json', 'r+') as json_data:
                tasks = json.load(json_data)
        if not task in tasks:
            tasks[task] = {}
        tasks[task]["status"] = value
        with open('data/tasks.json', 'w+') as json_data:
            json.dump(tasks, json_data)

    async def get_task_status(self, task):
        tasks = {}
        if os.path.isfile('data/tasks.json'):
            with open('data/tasks.json', 'r+') as json_data:
                tasks = json.load(json_data)
        if task in tasks and "status" in tasks[task]:
            return tasks[task]["status"]
        return None


class Api:
    base_url:str
    user:str
    key:str

    def __init__(self, request_ass, api_conf):
        self.request_ass = request_ass
        if api_conf:
            if 'API_URL' in api_conf:
                self.base_url = api_conf['API_URL']
            else:
                v_print(-1, "API URL MISSING")
            if 'USER' in api_conf:
                self.user = api_conf['USER']
            else:
                v_print(-1, "API USER MISSING")
            if 'KEY' in api_conf:
                self.key = api_conf['KEY']
            else:
                v_print(-1, "API KEY MISSING")
        else:
            v_print(-1, "Api config is missing!")

    async def can_api(self):
        if self.base_url:
            return True
        return False

    async def can_auth(self):
        return await self.can_api() and self.user and self.key

    async def get_req(self, path):
        if await self.can_api():
            # Create a set of unsent Requests
            urls = [self.base_url + path]
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

    async def post_req(self, path, data):
        if await self.can_auth():
            urls = [self.base_url + path]
            requests = (self.request_ass.post(url, json=data, auth=(self.user, self.key)) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api keys"}

    async def delete_req(self, path, data):
        if await self.can_auth():
            urls = [self.base_url + path]
            requests = (self.request_ass.delete(url, json=data, auth=(self.user, self.key)) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api keys"}


    async def patch_req(self, path, data):
        if await self.can_auth():
            urls = [self.base_url + path]
            requests = (self.request_ass.patch(url, json=data, auth=(self.user, self.key)) for url in urls)
            response = await self.handle_request(requests)
            return response
        return {"success": False, "content": "Missing api keys"}


def is_float(element) -> bool:
    #If you expect None to be passed:
    if element is None:
        return False
    try:
        float(element)
        return True
    except ValueError:
        return False
