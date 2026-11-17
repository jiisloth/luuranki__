import datetime
import os
from xmlrpc.client import DateTime

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from components.verbosity import v_print


class Gsheets:
    def __init__(self):
        if not os.path.isfile("secret.json"):
            v_print(-1, "secret.json is missing!")
            return
        self.client = self._connect("secret.json")

    def _connect(self, secret_path):
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(secret_path, scope)
        client = gspread.authorize(creds)
        return client

    def fetch_from_sheets(self, sheet_name, tab, cell_range=None):
        sheet = self.client.open(sheet_name)
        result = sheet.worksheet(tab).get(cell_range)
        v_print(3, result)
        return result

    def update_sheet_cell(self, sheet_name, tab, row, col, value):
        sheet = self.client.open(sheet_name).worksheet(tab)
        sheet.update_cell(row, col, str(value))
        return

    def add_new_minigolf_line(self, content, current_hole, sender):
        sheet = self.client.open("Daily Minigolf Challenge").worksheet("SubmitScore")
        res = sheet.get("D2:G1000")
        v_print(3, res)
        for r in range(len(res)):
            row = res[r]
            if len(row) > 3 and str(row[0]) == str(current_hole) and sender == row[3]:
                return False
        sheet.update_cell(len(res)+2, 2, content)
        self.update_timestamp("Töimisto Visual information system TeleVision", "DataMinigolf", 1, 4)
        return True


    def update_timestamp(self, sheet_name, tab, row, col):
        self.update_sheet_cell(sheet_name, tab, row, col, datetime.datetime.now())
        return