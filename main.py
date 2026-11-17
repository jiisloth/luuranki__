import asyncio

from gevent import monkey

monkey.patch_all()
import grequests
import os


import configparser

from components.bot import init_bot, Bot

CFG_FILE_NAME = 'config.ini'

required_cfg_values = {
    'BOT': ['DISCORD_BOT_TOKEN', 'SUPER_ADMIN'],
    'API': ['API_URL', 'USER', 'KEY']
}





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
    config = read_config()
    bot:Bot = init_bot(config, grequests)
    asyncio.create_task(testloop())
    await bot.start(config['BOT']['DISCORD_BOT_TOKEN'])

async def testloop(): # lol async too hard. this seems to work tho.
    while True:
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
