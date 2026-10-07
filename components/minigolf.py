import asyncio
from datetime import datetime, timezone, time, timedelta
from typing import Union, TYPE_CHECKING
from discord import TextChannel, Thread, Message
from components.googlesheets import Gsheets

import pytz
from components.verbosity import v_print

if TYPE_CHECKING:
    from components.bot import Bot

class SheetOperator:
    def __init__(self, sheet_name, tabs):
        self.gsheets = Gsheets()
        self.tabs = tabs
        self.sheet_name = sheet_name

class TabOperator:
    def __init__(self):
        pass

class MinigolfTabs(TabOperator):
    settings = None
    submit = None
    output = None
    gamedays = None
    def __init__(self, tabs_conf):
        super().__init__()
        if "settings" in tabs_conf:
            self.settings = tabs_conf["settings"]
        if "submit" in tabs_conf:
            self.submit = tabs_conf["submit"]
        if "output" in tabs_conf:
            self.output = tabs_conf["output"]
        if "gamedays" in tabs_conf:
            self.gamedays = tabs_conf["gamedays"]



class MinigolfSheet(SheetOperator):
    tabs: MinigolfTabs
    score_range = "D2:G1000"
    gameday_range = "A2:G100"


    def __init__(self, sheet_conf):
        super().__init__(sheet_conf["sheet_name"], MinigolfTabs(sheet_conf["tabs"]))

    def submit_score(self, score_string, hole_number, sender):
        result = self.gsheets.fetch_from_sheets(self.sheet_name, self.tabs.submit, self.score_range)
        for r in range(len(result)):
            row = result[r]
            if len(row) > 3 and str(row[0]) == str(hole_number) and sender == row[3]:
                return False
        self.gsheets.update_sheet_cell(self.sheet_name, self.tabs.submit, len(result) + 2, 2, score_string)
        return True

    def get_settings(self):
        return self.gsheets.fetch_from_sheets(self.sheet_name, self.tabs.settings)

    def get_gamedays(self):
        return self.gsheets.fetch_from_sheets(self.sheet_name, self.tabs.gamedays, self.gameday_range)

    def update_timestamp(self):
        self.gsheets.update_timestamp(self.sheet_name, self.tabs.output, 3, 9)

    def get_thread_title_and_message(self):
        ttm = self.gsheets.fetch_from_sheets(self.sheet_name, self.tabs.output, "ThreadTitleContent")
        if len(ttm) == 2:
            return {"title": ttm[0][0], "message": ttm[1][0]}
        v_print(-1, "Could not fetch Title and message!")
        return None

class MinigolfSettings:
    raw = {}
    parsed = False
    hole_start_time: time
    start_date: datetime
    count_weekends: bool
    hole_count: int
    sheet_tz = "Europe/Helsinki"
    gamedays = {}

    def __init__(self, ms:MinigolfSheet):
        data = ms.get_settings()
        settings = {}

        for row in data:
            if len(row) == 2:
                key = row[0].lower().strip().replace(" ", "_")
                if key == "sheet_timezone":
                    settings[key] = row[1].strip()
                    self.sheet_tz = row[1].strip()
        for row in data:
            if len(row) == 2:
                self.raw[row[0]] = row[1]
                key = row[0].lower().strip().replace(" ", "_")
                if key == "hole_start_time":
                    hm = row[1].strip().split(":")
                    if len(hm) >= 2 and hm[0].isdigit() and hm[1].isdigit():
                        dt = time(hour=int(hm[0]), minute=int(hm[1]), tzinfo=pytz.timezone(self.sheet_tz))
                        settings[key] = dt
                        self.hole_start_time = dt
                if key == "start_date":
                    dd = row[1].strip().split("/")
                    if len(dd) >= 3 and dd[0].isdigit() and dd[1].isdigit() and dd[2].isdigit():
                        dt = datetime(year=int(dd[2]), month=int(dd[1]), day=int(dd[0]), tzinfo=pytz.timezone(self.sheet_tz))
                        settings[key] = dt
                        self.start_date = dt
                if key == "count_weekends":
                    if row[1].strip() == "FALSE":
                        settings[key] = False
                    else:
                        settings[key] = True
                    self.count_weekends = settings[key]
                if key == "hole_count":
                    if row[1].strip().isdigit():
                        settings[key] = int(row[1].strip())
                        self.hole_count = settings[key]

        required_keys = ["hole_start_time", "start_date", "count_weekends", "hole_count","sheet_timezone"]
        success = True
        for x in range(len(required_keys)):
            if not required_keys[x] in settings:
                success = False
                v_print(-1, "Missing settings key/value for '" + required_keys[x] + "'!")
        v_print(3, settings)
        gd_data = ms.get_gamedays()
        self.setup_gamedays(gd_data)
        if len(self.gamedays.keys()) != self.hole_count:
            v_print(-1, "Gamedays not parsed properly")
            success = False
        self.parsed = success


    def setup_gamedays(self, data):
        self.gamedays = {}
        for row in data:
            if len(row) == 7:
                if row[4] == "FALSE":
                    hnum = None
                    if row[5].isdigit():
                        hnum = int(row[5])
                        if hnum > self.hole_count:
                            print("TOO BIG HNUM", hnum)
                            break
                    else:
                        v_print(-1, "Non integer hole number in sheet! " + row[5])
                    dt = None
                    dd = row[0].strip().split("/")
                    if len(dd) >= 3 and dd[0].isdigit() and dd[1].isdigit() and dd[2].isdigit():
                        dt = datetime(year=int(dd[2]), month=int(dd[1]), day=int(dd[0]), hour=self.hole_start_time.hour, minute=self.hole_start_time.minute, tzinfo=pytz.timezone(self.sheet_tz))
                    if dt and hnum:
                        self.gamedays[hnum] = dt
                    else:
                        v_print(-1, "Could not parse date! " + row[0])
        v_print(3, self.gamedays)


    def get_hole_date(self, hnum:int):
        if hnum in self.gamedays:
            return self.gamedays[hnum]
        return None

    def utc_to_sheet_time(self, dt):
        return dt.replace(tzinfo=timezone.utc).astimezone(tz=pytz.timezone(self.sheet_tz))

    def sheet_time_now(self):
        return self.utc_to_sheet_time(datetime.now(timezone.utc))

    def sheet_time_to_utc(self, dt):
        return dt.replace(tzinfo=pytz.timezone(self.sheet_tz)).astimezone(tz=pytz.timezone('UTC'))




class Minigolf:
    game_thread:Union[Thread, None] = None
    spoiler_thread:Union[Thread, None] = None
    game_channel:Union[TextChannel, None] = None
    played_today = []
    current_hole = -1
    is_game_day = False
    should_stop = False
    bot:Bot = None
    sheets: MinigolfSheet
    settings: MinigolfSettings
    looping = False

    def __init__(self, bot, ms:MinigolfSheet, game_channel:Union[TextChannel, None]):
        self.sheets = ms
        self.settings = MinigolfSettings(ms)
        self.bot = bot
        self.game_channel = game_channel

    async def stop(self):
        self.should_stop = True

    async def start(self):
        await self.daily_action_loop()

    async def make_daily_thread(self, title:str, message:str):
        self.played_today = []
        if self.game_channel:
            after = self.settings.utc_to_sheet_time(self.settings.start_date)
            self.game_thread, is_new = await self.bot.get_or_create_thread(self.game_channel, title, after, True, message, True)
            if not is_new:
                await self.make_daily_spoiler_thread(title.split(" | ")[0] + " | Spoilers")
                await self.bot.loop_over_message_history(self.game_thread, self.check_if_marked)
                return True, False
            await self.make_daily_spoiler_thread(title.split(" | ")[0] + " | Spoilers")
            return True, True
        return False, False

    async def check_hole_post(self, hole_arg):
        ttm = self.sheets.get_thread_title_and_message()
        if ttm:
            hole = ttm["title"].split(" ")[0]
            reply = None
            if len(hole) > 1 and hole[1:].is_digit():
                hole = int(hole[1:])
                if hole_arg > 0:
                    if hole_arg == hole and self.current_hole != hole:
                        reply = f'Mää luulin että pitäs olla reikä {self.current_hole} mut sanoit että ois {hole_arg} ja sheetistä löyty reikä {hole}... Korjaan tilanteen...'
                        self.current_hole = hole
                    elif hole_arg == self.current_hole and hole != hole_arg:
                        reply = f'Sheetistä tullee väärää reikää :('
                elif self.current_hole != hole:
                    reply = f'No tota.. Sheetistä tulee reikä #{hole} ja mun mielestä pitäs olla #{self.current_hole}'
                if self.current_hole == hole and (hole_arg == -1 or hole_arg == hole):
                    success, created = await self.make_daily_thread(ttm["title"], ttm["message"])
                    if success:
                        if not created:
                            reply = f'No eiks se oo tää: {self.game_thread.jump_url} ?'
                        else:
                            reply = f'💀'
                return True, reply
        return False, None

    async def make_daily_spoiler_thread(self, title:str):
        if self.game_channel:
            after = self.settings.utc_to_sheet_time(self.settings.start_date)
            self.spoiler_thread, is_new = await self.bot.get_or_create_thread(self.game_channel, title, after, False)
            return is_new
        self.spoiler_thread = None
        return False


    async def check_if_marked(self, msg:Message):
        checked = False
        for r in msg.reactions:
            if r.me or (isinstance(r.emoji, str) and (r.emoji == "❎" or r.emoji == "✅")):
                checked = True
                break
        if not checked:
            await self.check_if_score_message(msg)
        return {"halt": False}

    async def check_if_score_message(self, message):
        score_msg = await self.parse_score_message(message.content)
        if score_msg:
            await message.add_reaction("👏")
            await message.add_reaction("🤔")
            sender = await self.bot.get_nick(message.author)
            created = self.settings.utc_to_sheet_time(message.created_at)
            timestamp = "[" + str(created.hour).zfill(2) + ":" + str(created.minute).zfill(2) + "]"
            score_msg = timestamp + sender + ": " + score_msg + " 🤖 Added by luuranki"
            res = self.sheets.submit_score(score_msg, self.current_hole, sender)
            await message.remove_reaction("🤔", self.bot.user)
            if res:
                await message.add_reaction("✅")
                await self.bot.invite_to_thread(self.spoiler_thread, message.author)
            else:
                await message.add_reaction("❎")
                await asyncio.sleep(5)
                await message.add_reaction("💀")

    async def parse_score_message(self, msg):
        lines = msg.split("\n")
        for l in range(len(lines)):
            words = lines[l].split(" ")
            if l == 0 and len(words) > 1 and (words[0] == "flex" or (words[0] == "#" and words[1] == "flex")):
                return None
            if "putt.day" in words:
                start = words.index("putt.day")
                if len(words) - start >= 4:
                    if "⛳" in words:
                        if words.index("⛳") == start + 2:
                            if len(words[start + 3].split("/")) == 2:
                                return " ".join(words[start:start + 4])
                v_print(3, "putt.day but not a score message?")
                v_print(3, words)
        return None

    async def daily_action_loop(self):
        if self.looping:
            return
        self.looping = True
        self.current_hole = 0
        v_print(2, "Starting loop")
        await self.bot.save_task_status("minigolf", "running")
        await self.wait_for_ready()
        day = timedelta(days=1)
        while self.current_hole < self.settings.hole_count:
            v_print(2, self.current_hole)
            if self.should_stop:
                return
            current_date = self.settings.get_hole_date(self.current_hole)
            next_date = self.settings.get_hole_date(self.current_hole+1)
            now = self.settings.sheet_time_now()
            if current_date:
                if current_date < now:
                    if now < current_date + day:
                        self.is_game_day = True
                        await self.do_daily_actions()
                    else:
                        self.is_game_day = False
                else:
                    next_date = current_date
            if not next_date:
                if current_date and now < current_date + day:
                    to_over = (current_date + day) - now
                    v_print(1, "Last day!")
                    await asyncio.sleep(to_over.seconds)
                break
            if next_date < now:
                self.current_hole += 1
                continue
            to_next:timedelta = next_date - now
            if to_next < day:
                await asyncio.sleep(to_next.seconds + 1)
                self.current_hole += 1
                self.is_game_day = True
            else:
                await asyncio.sleep(day.seconds + 1)
        if self.should_stop:
            return
        await self.bot.save_task_status("minigolf", "ended")
        self.bot.minigolf = None
        v_print(1, "game ended!")
        self.is_game_day = False
        self.looping = False

    async def do_daily_actions(self):
        v_print(1, "Hole #" + str(self.current_hole).ljust(2, " "), self.settings.sheet_time_now())
        self.sheets.update_timestamp()
        ttm = self.sheets.get_thread_title_and_message()
        if ttm:
            await self.make_daily_thread(ttm["title"], ttm["message"])

    async def wait_for_ready(self):
        w = 0
        while True:
            if self.should_stop:
                return
            if self.bot.is_ready:
                if self.game_channel:
                    break
                if w < 2:
                    v_print(1, "Bot game channel not setup")
                    w = 2
            if w == 0:
                v_print(1, "Waiting for bot ready...")
                w = 1
            await asyncio.sleep(2)
        return



async def old_ass_create_minigolf_loop(bot, gsheets, loc_tz):
    global local_tz
    local_tz = loc_tz
    settings_parsed, settings, raw_settings = old_ass_get_settings(gsheets)
    if not settings_parsed:
        v_print(-1, "raw settings:")
        v_print(-1, raw_settings)
        return
    v_print(3, settings)
    w = 0
    while True:
        if bot.is_ready:
            if bot.game_channel:
                break
            if w < 2:
                v_print(1, "Bot game channel not setup")
                w = 2
        if w == 0:
            v_print(1, "Waiting for bot ready...")
            w = 1
        await asyncio.sleep(2)
    while True:
        sd:datetime = settings["start_date"]
        st:datetime = settings["hole_start_time"]
        tz = pytz.timezone(local_tz)
        next_hole = tz.localize(datetime(year=sd.year, month=sd.month, day=sd.day, hour=st.hour,minute=st.minute))
        current_hole = 0
        v_print(1, "starting loop")
        while current_hole < settings["hole_count"]:
            now = current_time_in_tz()
            if now > next_hole:
                if not settings["count_weekends"] and next_hole.weekday() > 4:
                    v_print(1, "IS WKND!", next_hole, current_time_in_tz())
                    next_hole += timedelta(days=1)
                else:
                    v_print(1, "Hole #" + str(current_hole+1).ljust(2, " "), next_hole, current_time_in_tz())
                    next_hole += timedelta(days=1)
                    current_hole += 1
                    if now < next_hole:
                        gsheets.update_timestamp("Daily Minigolf Challenge", "Outputs", 3, 9)
                        ttc = gsheets.fetch_from_sheets("Daily Minigolf Challenge", "Outputs", "ThreadTitleContent")
                        if len(ttc) == 2:
                            bot.current_hole = current_hole
                            await bot.make_new_thread(ttc[0][0], ttc[1][0])
            if now < next_hole:
                await asyncio.sleep((next_hole - now).seconds)
        v_print(1, "All holes doned!")

        v_print(1, "Waiting for new tourney..")
        waited_days = 0
        while True:
            settings_parsed, settings, raw_settings = old_ass_get_settings(gsheets)
            if settings_parsed:
                if sd != settings["start_date"]:
                    break
            if waited_days > 35:
                #make bot give up if no tournament starts in over month..
                return
            await asyncio.sleep(60*60*24)
            waited_days += 1




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
            v_print(2, "putt.day but not a score message?")
            v_print(2, words)
    return None

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=pytz.timezone(local_tz))

def current_time_in_tz():
    return utc_to_local(datetime.now(timezone.utc))
