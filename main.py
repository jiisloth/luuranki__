import random
from datetime import time, datetime, timedelta, timezone
import os
import asyncio

import pytz

import googleSheets.googlesheets as gs


import discord
import configparser

CFG_FILE_NAME = 'config.ini'

required_cfg_values = {
    'BOT': ['DISCORD_BOT_TOKEN', 'SUPER_ADMIN'],
    'GSHEETS': ['secret_path']
}

local_tz = "Europe/Helsinki"




def read_config():
    no_file = False
    if not os.path.exists(CFG_FILE_NAME):
        open(CFG_FILE_NAME, 'a').close()
        no_file = True
    config = configparser.ConfigParser()
    config.read(CFG_FILE_NAME)
    config.sections()
    missing = []
    for section in required_cfg_values.keys():
        if section not in config:
            config.add_section(section)
        for option in required_cfg_values[section]:
            if option not in config[section] or not config[section][option] or config[section][option] == '<REQUIRED VALUE>':
                missing.append(option)
                config.set(section, option, '<REQUIRED VALUE>')
    if missing:
        save_config_file(config)
        if no_file:
            raise Exception('Config file missing! Created {} at {}. Please fill required values.'.format(CFG_FILE_NAME, os.getcwd()))

        raise Exception('Missing required configuration values: {}\nPlease fix {}'.format(missing, CFG_FILE_NAME))
    return config


def init_bot(cfg, gsheets):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    client = Bot(intents=intents)
    client.configure(cfg, gsheets)
    return client

async def run_bot(bot, token):
    print("running bot")
    await bot.start(token)

def save_config_file(config):
    with open(CFG_FILE_NAME, 'w') as configfile:
        config.write(configfile)


async def main():
    global local_tz
    config = read_config()
    if 'GLOBAL' in config and 'timezone' in config['GLOBAL']:
        local_tz = config['GLOBAL']['timezone']

    gsheets = gs.Gsheets(config['GSHEETS']['secret_path'])
    settings_parsed, settings, raw_settings = get_settings(gsheets)
    if not settings_parsed:
        print("raw settings:")
        print(raw_settings)
        return
    bot = init_bot(config["BOT"], gsheets)
    asyncio.create_task(create_daily_loop(settings, bot, gsheets))
    await bot.start(config['BOT']['DISCORD_BOT_TOKEN'])

async def create_daily_loop(settings, bot, gsheets):
    global local_tz
    while True:
        if bot.is_initialized():
            break
        print("waiting for bot")
        await asyncio.sleep(10)
    sd:datetime = settings["start_date"]
    st:datetime = settings["hole_start_time"]
    tz = pytz.timezone(local_tz)
    next_hole = tz.localize(datetime(year=sd.year, month=sd.month, day=sd.day, hour=st.hour,minute=st.minute))
    current_hole = 0
    print("starting loop")
    while current_hole < settings["hole_count"]:
        now = current_time_in_tz()
        if now > next_hole:
            if not settings["count_weekends"] and next_hole.weekday() > 4:
                print("IS WKND!", next_hole, current_time_in_tz())
                next_hole += timedelta(days=1)
            else:
                print("Hole #" + str(current_hole+1).ljust(2, " "), next_hole, current_time_in_tz())
                next_hole += timedelta(days=1)
                current_hole += 1
                if now < next_hole:
                    ttc = gsheets.fetchfromsheets("Daily Minigolf Challenge", "DiscordThreadCopyPasta", "ThreadTitleContent")
                    if len(ttc) == 2:
                        bot.current_hole = current_hole
                        await bot.make_new_thread(ttc[0][0], ttc[1][0])
        if now < next_hole:
            await asyncio.sleep((next_hole - now).seconds)
    print("All holes doned!")




def get_settings(gsheets):
    data = gsheets.fetchfromsheets("Daily Minigolf Challenge", "Settings")
    settings = {}
    raw_settings = {}
    for row in data:
        if len(row) == 2:
            raw_settings[row[0]] = row[1]
            key = row[0].lower().strip().replace(" ", "_")
            if key == "hole_start_time":
                hm = row[1].strip().split(":")
                if len(hm) >= 2 and hm[0].isdigit() and hm[1].isdigit():
                    dt = time(hour=int(hm[0]), minute=int(hm[1]))
                    settings[key] = dt
            if key == "start_date":
                dd = row[1].strip().split("/")
                if len(dd) >= 3 and dd[0].isdigit() and dd[1].isdigit() and dd[2].isdigit():
                    dt = datetime(year=int(dd[2]), month=int(dd[1]), day=int(dd[0]))
                    settings[key] = dt
            if key == "count_weekends":
                if row[1].strip() == "FALSE":
                    settings[key] = False
                else:
                    settings[key] = True
            if key == "hole_count":
                if row[1].strip().isdigit():
                    settings[key] = int(row[1].strip())
    required_keys = ["hole_start_time", "start_date", "count_weekends", "hole_count"]
    success = True
    for x in range(len(required_keys)):
        if not required_keys[x] in settings:
            success = False
            print("Missing settings key/value for '" + required_keys[x] + "'!")
    return success, settings, raw_settings


class Bot(discord.Client):
    config = None
    current_thread = None
    game_channel = None
    pending_channel_ids = {}
    channels = {}
    super_admin = []
    played = []
    gsheets = None
    current_hole = -1
    is_ready = False

    def configure(self, config, gsheets):
        self.gsheets = gsheets
        admins = config['SUPER_ADMIN'].split(",")
        for a in range(len(admins)):
            self.super_admin.append(int(admins[a]))
        self.pending_channel_ids[config['gaming_channel_id']] = "game_channel"


    def is_initialized(self):
        if self.is_ready and self.game_channel:
            return True
        return False

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
        if message.author.id in self.super_admin and message.content.lower() == "!gamingchannel":
            self.game_channel = message.channel
            await message.add_reaction("☑️")
        if message.content.lower() == "haloo":
            if random.random() > 0.5:
                await message.reply("haloo?")
            else:
                await message.reply("haloo!")
        if message.content.lower() == "haloo?":
            await message.reply("haloo!")
        if message.content.lower() == "haloo!":
            await message.reply("haloo?")

        if self.current_thread and message.channel.id == self.current_thread.id:
            await self.check_if_score_message(message)

    async def check_if_score_message(self, message):
        score_msg = await get_score_message(message.content)
        if score_msg:
            await message.add_reaction("👏")
            await message.add_reaction("🤔")
            sender = message.author.display_name
            created = utc_to_local(message.created_at)
            timestamp = "[" + str(created.hour).zfill(2) + ":" + str(created.minute).zfill(2) + "]"
            score_msg = timestamp + sender + ": " + score_msg + " 🤖 Added by luuranki"
            res = self.gsheets.add_new_line(score_msg, self.current_hole, sender)
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

    async def make_new_thread(self, title, content):
        self.played = []
        if self.game_channel:
            threads = self.game_channel.threads
            for t in range(len(threads)):
                thread = threads[t]
                if thread.name == title:
                    self.current_thread = thread
                    await self.check_message_history()
                    return
            self.current_thread = await self.game_channel.create_thread(name=title, type=discord.ChannelType.public_thread)
            mentions_fix = await self.make_mentions(content)
            await self.current_thread.send(mentions_fix)

    async def make_mentions(self, content:str):
        roles = self.game_channel.guild.roles
        for role in roles:
            if role.mentionable:
                n = "@" + role.name
                content = content.replace(n, role.mention)
        return content


async def get_score_message(msg):
    lines = msg.split("\n")
    for l in range(len(lines)):
        words = lines[l].split(" ")
        if "putt.day" in words:
            start = words.index("putt.day")
            if len(words) - start >= 4:
                if "⛳" in words:
                    if words.index("⛳") == start + 2:
                        if len(words[start+3].split("/")) == 2:
                            return " ".join(words[start:start+4])
            print("putt.day but not a score message?")
            print(words)
    return None

def utc_to_local(utc_dt):
    global local_tz
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=pytz.timezone(local_tz))

def current_time_in_tz():
    return utc_to_local(datetime.now(timezone.utc))






if __name__ == '__main__':
    asyncio.run(main())
