import asyncio
from datetime import datetime, timezone, time, timedelta

import pytz


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



async def create_minigolf_loop(bot, gsheets):
    global local_tz

    settings_parsed, settings, raw_settings = get_settings(gsheets)
    if not settings_parsed:
        print("raw settings:")
        print(raw_settings)
        return
    w = 0
    while True:
        if bot.is_ready:
            if bot.game_channel:
                break
            if w < 2:
                print("Bot game channel not setup")
                w = 2
        if w == 0:
            print("Waiting for bot ready...")
            w = 1
        await asyncio.sleep(2)
    while True:
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

        print("Waiting for new tourney..")
        waited_days = 0
        while True:
            settings_parsed, settings, raw_settings = get_settings(gsheets)
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
            print("putt.day but not a score message?")
            print(words)
    return None

def utc_to_local(utc_dt):
    global local_tz
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=pytz.timezone(local_tz))

def current_time_in_tz():
    return utc_to_local(datetime.now(timezone.utc))
