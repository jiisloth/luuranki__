import gspread
from oauth2client.service_account import ServiceAccountCredentials


class Gsheets:
    def __init__(self, secret_path):
        self.client = self._connect(secret_path)

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

    def add_new_line(self, content, current_hole, sender):
        sheet = self.client.open("Daily Minigolf Challenge").worksheet("SubmitScore")
        res = sheet.get("D2:G1000")
        for r in range(len(res)):
            row = res[r]
            if str(row[0]) == str(current_hole) and sender == row[3]:
                return False
        sheet.update_cell(len(res)+2, 2, content)
        return True