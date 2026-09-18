
from gevent import monkey
monkey.patch_all()
import grequests
import os
import asyncio


import components.googlesheets as gs

import configparser

from components.bot import init_bot
from components.minigolf import create_minigolf_loop
from components.roleChecker import create_role_check_loop

CFG_FILE_NAME = 'config.ini'

required_cfg_values = {
    'BOT': ['DISCORD_BOT_TOKEN', 'SUPER_ADMIN'],
    'API': ['API_URL', 'USER', 'KEY']
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


def save_config_file(config):
    with open(CFG_FILE_NAME, 'w') as configfile:
        config.write(configfile)


async def main():
    global local_tz
    config = read_config()


    if 'GLOBAL' in config and 'timezone' in config['GLOBAL']:
        local_tz = config['GLOBAL']['timezone']

    gsheets = gs.Gsheets()
    bot = init_bot(config, gsheets, grequests)
    asyncio.create_task(create_minigolf_loop(bot, gsheets))
    asyncio.create_task(create_role_check_loop(bot))
    await bot.start(config['BOT']['DISCORD_BOT_TOKEN'])




if __name__ == '__main__':

    #p = requests.get("http://127.0.0.1:5000/keyvalue/perttiStuck")
    #print(p.json())
    asyncio.run(main())
