import datetime
import os
from xmlrpc.client import DateTime

import gspread
from oauth2client.service_account import ServiceAccountCredentials


class Gsheets:
    def __init__(self):
        if not os.path.isfile("secret.json"):
            print("secret.json is missing!")
            return
        self.client = self._connect("secret.json")

    def _connect(self, secret_path):
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(secret_path, scope)
        client = gspread.authorize(creds)
        return client

    def fetchfromsheets(self, sheetname, tab, range=None):
        sheet = self.client.open(sheetname)
        result = sheet.worksheet(tab).get(range)
        return result

    def add_new_minigolf_line(self, content, current_hole, sender):
        sheet = self.client.open("Daily Minigolf Challenge").worksheet("SubmitScore")
        res = sheet.get("D2:G1000")
        for r in range(len(res)):
            row = res[r]
            if str(row[0]) == str(current_hole) and sender == row[3]:
                return False
        sheet.update_cell(len(res)+2, 2, content)
        self.set_update_value("Töimisto Visual information system TeleVision", "DataMinigolf", 1, 4)
        return True


    def set_update_value(self, sheet, tab, row, col):
        sheet = self.client.open(sheet).worksheet(tab)
        sheet.update_cell(row, col, str(datetime.datetime.now()))
        return True