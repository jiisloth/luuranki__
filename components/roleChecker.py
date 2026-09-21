import asyncio
import json


local_tz = "Europe/Helsinki"


async def create_role_check_loop(bot, loc_tz):
    global local_tz
    local_tz = loc_tz
    while True:
        with open('data/rolemessage.json') as json_data:
            rolemsgs = json.load(json_data)
        valid = []
        changes = False
        for rm in rolemsgs:
            ok, delet = bot.check_role_msg(rm)
            if not delet:
                valid.append(rm)
            else:
                changes = True
        if changes:
            with open('data/rolemessage.json') as json_data:
                json.dump(valid, json_data)
        await asyncio.sleep(60*10)


async def add_role_checker_entry(role, emoji, msg, channel):
        with open('data/rolemessage.json') as json_data:
            rolemsgs = json.load(json_data)
        rolemsgs.append({"msg": msg, "role": role, "emoji": emoji, "channel": channel})
        with open('data/rolemessage.json') as json_data:
            json.dump(rolemsgs, json_data)

