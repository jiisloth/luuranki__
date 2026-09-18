import asyncio
import json


async def create_role_check_loop(bot):
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

