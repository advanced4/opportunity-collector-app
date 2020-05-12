# author: jf

import csv
import json
import os
import platform
import random
import threading
import time
from datetime import datetime, timedelta
from functools import partial
from os import listdir
from os.path import isfile, join, sep
from sys import exit
from tkinter import *

import requests

try:
    from win32ui import messagebox
except ImportError:
    from tkinter import messagebox

'''############### GLOBALS // CONSTANTS #######################'''
bug_user_about_expired_key = True
key_expiry_days = 90
cfg_sam_keys = ["sam_enabled", "sam_api_key", "sam_types", "sam_naics"]
# based on https://open.gsa.gov/api/get-opportunities-public-api/ which omits "o" >_>
sol_typ_plain_abv_map = {"sam_justification": "u", "sam_presol": "p", "sam_award_notice": "a", "sam_sources_sought": "r", "sam_special_notice": "s", "sam_surplus_property": "g",
                         "sam_combined_syn_sol": "k", "sam_solicitation": "o", "sam_intent_bundle": "i"}
sol_typ_abv_plain_map = {value: key for key, value in sol_typ_plain_abv_map.items()}
script_path = os.path.dirname(os.path.realpath(__file__))
conf_path = script_path + sep + "config.json"
if platform.system() == "Darwin":
    import getpass
    username = getpass.getuser()
    outdir = "/Users/" + username + "/Documents/"
else:
    outdir = script_path + sep

sam_endpoint = "https://api.sam.gov/prod/opportunities/v1/search"
grants_endpoint = "https://www.grants.gov/grantsws/rest/opportunities/search/csv/download?osjp="
today = datetime.now().strftime('%m/%d/%Y')
today_dt = datetime.strptime(today, '%m/%d/%Y')

# ref https://www.grants.gov/help/html/help/index.htm?rhcsh=1&callingApp=custom#t=XMLExtract%2FXMLExtract.htm
grants_fund_instruments_plain_abv = {"Grant": "G", "Cooperative Agreement": "CA", "Procurement Contract": "PC", "Other": "O"}
grants_fund_instruments_abv_plain = {value: key for key, value in grants_fund_instruments_plain_abv.items()}
grants_eligibilities_plain_abv = {"Unrestricted": "99", "Nonprofits 501C3": "12", "Nonprofits non 501C3": "13",
                                  "Private institutions of higher education": "20", "Individuals": "21", "For-profit organizations other than SB": "22",
                                  "Small businesses": "23", "Others": "25"}  # all government entities are omitted + tribal entities
grants_eligibilities_abv_plain = {value: key for key, value in grants_eligibilities_plain_abv.items()}
grants_cats_abv_plain = {"BC": "Business & Commerce",
                         "CD": "Community Development", "CP": "Consumer Protection", "DPR": "Disaster Prevention & Relief",
                         "ED": "Education", "ELT": "Employment, Labor and Training", "EN": "Energy",
                         "ENV": "Environment", "HL": "Health",
                         "HU": "Humanities", "IS": "Information and Statistics",
                         "LJL": "Law, Justice and Legal Services", "NR": "Natural Resources", "RA": "Recovery Act", "RD": "Regional Development",
                         "ST": "Science & Technology and other R&D",
                         "T": "Transportation", "O": "Other", "ACA": "Affordable Care Act",
                         "AG": "Agriculture", "AR": "Arts", "FN": "Food & Nutrition", "HO": "Housing", "ISS": "Income Security & Social Services"}
grants_cats_plain_abv = {value: key for key, value in grants_cats_abv_plain.items()}
cfg = {}
global sam_gui
global grants_gui
'''############################################################'''


def get_latest_csv(ending):
    latest_time = 0
    onlyfiles = [f for f in listdir(script_path) if (isfile(join(script_path, f)) and f.endswith(ending + ".csv"))]

    for f in onlyfiles:
        tt = int(os.path.getmtime(f))

        if tt > latest_time:
            latest_time = tt

    if latest_time > 0.0:
        return datetime.utcfromtimestamp(latest_time).strftime("%m/%d/%Y")
    else:
        return None


def toggle_sam_sol_type(sol_type):
    # at first I wanted to do something like sam_gui["sam_" + sol_type] but thats not allowed
    # but this works too, so thats nice
    cb = getattr(sam_gui, "sam_" + sol_type)

    if sol_type in cfg["sam_types"]:
        cfg["sam_types"].remove(sol_type)
        cb.deselect()
    else:
        cfg["sam_types"].append(sol_type)
        cb.select()


def toggle_grants_inst(inst):
    cb = getattr(grants_gui, "inst_" + inst)

    if inst in cfg["grants_instruments"]:
        cfg["grants_instruments"].remove(inst)
        cb.deselect()
    else:
        cfg["grants_instruments"].append(inst)
        cb.select()


def toggle_grants_cat(cat):
    cb = getattr(grants_gui, "cat_" + cat)

    if cat in cfg["grants_cats"]:
        cfg["grants_cats"].remove(cat)
        cb.deselect()
    else:
        cfg["grants_cats"].append(cat)
        cb.select()


def toggle_grants_elig(elig):
    cb = getattr(grants_gui, "elig_" + elig)

    if elig in cfg["grants_eligibilities"]:
        cfg["grants_eligibilities"].remove(elig)
        cb.deselect()
    else:
        cfg["grants_eligibilities"].append(elig)
        cb.select()


def valid_date(datestring):
    try:
        datetime.strptime(datestring, '%m/%d/%Y')
        return True
    except ValueError:
        return False


def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def get_sam_opps():
    latest = get_latest_csv("__sam")
    if today == latest:
        sam_gui.get_button["state"] = "normal"
        yell_at_someone("Warning", "You already ran a search within the past 24 hours.\n"
                                   "This is OK to do within reason, but there are API limits.\n"
                                   "If you want to run it again, [re]move the latest result\n"
                                   "from the program folder")
        return

    from_date = sam_gui.from_date_e.get()
    to_date = sam_gui.to_date_e.get()

    if not valid_date(to_date) or not valid_date(from_date):
        sam_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "Date format is bad")
        return

    to_date_dt = datetime.strptime(to_date, '%m/%d/%Y')
    from_date_dt = datetime.strptime(from_date, '%m/%d/%Y')

    if from_date_dt > to_date_dt:
        sam_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "'To Date' must be greater than 'From Date'")
        return

    if to_date_dt > today_dt:
        sam_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "To Date can't be greater than today's date")
        return

    ncodes = cfg['sam_naics']
    ptypes = cfg["sam_types"]
    opps = []

    sam_gui.add_log("Starting collection...")
    for ptype in ptypes:
        for ncode_dict in ncodes:
            r = requests.get(sam_endpoint, params={'api_key': cfg["sam_api_key"], 'limit': 1000, 'postedFrom': from_date,
                                                   'postedTo': to_date, "ptype": ptype, "ncode": ncode_dict['code']})
            data = json.loads(r.text)
            if "error" in data:
                messagebox.showerror("Error", data['error']['code'])
                bye_global()
                # print(r.headers)
                return

            if "opportunitiesData" in data:
                opps.extend(data["opportunitiesData"])
                sam_gui.add_log("Found " + str(len(data['opportunitiesData'])) + " for NAICS: " + str(ncode_dict['code']) + " sol. type: " + sol_typ_abv_plain_map[ptype])
            else:
                sam_gui.add_log("No results for NAICS: " + str(ncode_dict['code']) + " solicitation type: " + ptype)

            if ptype == ptypes[-1] and ncode_dict == ncodes[-1]:
                # then this was the last iteration, so don't make the user wait any longer
                pass
            else:
                time.sleep(2)
    sam_gui.add_log("Done!")

    set_of_jsons = {json.dumps(d, sort_keys=True) for d in opps}
    opps = [json.loads(t) for t in set_of_jsons]

    if len(opps) > 0:
        keys = opps[0].keys()
        outfile = outdir + from_date.replace("/", "-") + "__" + to_date.replace("/", "-") + "__sam.csv"
        with open(outfile, 'w', newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(opps)
        messagebox.showinfo("Info", "Done! Output is at: " + outfile)
        bye_global()
        return
    sam_gui.get_button["state"] = "normal"
    yell_at_someone("Info", "No results")
    return


def get_grants():
    if not is_int(grants_gui.past_days.get()):
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "Bad value for date range")
        return

    past_days = int(grants_gui.past_days.get())

    if past_days > 365:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "Date range is too big")
        return

    if past_days < 1:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "Date range is too small")
        return

    past_date = datetime.now() - timedelta(past_days)

    outfile = outdir + past_date.strftime("%Y-%m-%d") + "__" + datetime.now().strftime("%Y-%m-%d") + "__grants.csv"

    if len(cfg["grants_cats"]) < 1:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "You must select at least one category")
        return
    if len(cfg["grants_instruments"]) < 1:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "You must select at least one instrument")
        return
    if len(cfg["grants_eligibilities"]) < 1:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", "You must select at least one eligibility")
        return

    params = {"startRecordNum": 0, "oppStatuses": "forecasted|posted", "sortBy": "openDate|desc", "rows": 9999, "eligibilities": "|".join(cfg["grants_eligibilities"]),
              "fundingCategories": "|".join(cfg["grants_cats"]), "fundingInstruments": "|".join(cfg["grants_instruments"]), "dateRange": past_days}

    # ya they have a weird api where they escape quotes, but not curly brackets or colons
    # so i can't use a normal URL encoder
    encoded_params = json.dumps(params).replace("\"", "%22").replace(" ", "")

    r = requests.get(grants_endpoint + encoded_params)
    if r.status_code == 200:
        with open(outfile, "w", encoding="utf-8") as of:
            of.write(r.text)
        grants_gui.get_button["state"] = "normal"
        messagebox.showinfo("Info", "Done! Output is at: " + outfile)
        bye_global()
        return
    elif r.status_code == 404:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Info", "No results")
    else:
        grants_gui.get_button["state"] = "normal"
        yell_at_someone("Error", r.status_code)


# This is just a bonus feature that isn't necessary, but will be nice
# as long as it lasts. Not clear on how stable this is -- looks like
# just a hobbyist behind it, but idk
def get_naics_description(code):
    url = "http://api.naics.us/v0/q?year=2012&code=" + str(code)
    res = requests.get(url)
    if res.status_code == 200:
        jres = json.loads(res.text)
        return jres["title"]
    else:
        return None


# save whatever the state of the config is
# and exit the python process
def bye_global():
    if cfg:
        write_new_config(cfg)

    # Must destroy any windows before exiting the python process
    if 'sam_gui' in globals():  # it may not exist yet if the user quits prior to it being drawn
        try:
            sam_gui.destroy()
        except TclError:
            # it may already be dead
            pass

    # it may not exist yet if the user quits prior to it being drawn
    # which is possible because theres a chance we prompt the user about an expiring api key
    if 'main_gui' in globals():
        try:
            main_gui.destroy()
        except TclError:
            # it may already be dead
            pass

    exit()


def do_grants_gui():
    pass


def write_new_config(new_conf):
    with open(conf_path, 'w') as f:
        json.dump(new_conf, f, indent=4)


def remove_sam_naics(code, elem_idx):
    global cfg

    sam_gui.elems[elem_idx].destroy()
    for entry in cfg['sam_naics']:
        if entry['code'] == code:
            cfg['sam_naics'].remove(entry)


def add_sam_naics():
    global cfg

    code = sam_gui.naics_entry.get()
    try:
        code = int(code)
        desc = get_naics_description(code)
    except ValueError:
        yell_at_someone("Error", "Entry must only contains numbers")
        return

    for entry in cfg['sam_naics']:
        if entry['code'] == code:
            yell_at_someone("Error", "Already exists")
            return

    new_entry = {'code': code, 'desc': desc}
    cfg['sam_naics'].append(new_entry)

    which_side = sam_gui.naics_right if how_many_children(sam_gui.naics_right) < how_many_children(sam_gui.naics_left) else sam_gui.naics_left
    txt = (str(code) + " - " + desc) if desc else (str(code) + " - " + "N/A")

    tmp = Frame(which_side)
    Label(tmp, text=txt).pack(side=LEFT)
    Button(tmp, text="Remove", width=10, command=partial(remove_sam_naics, code, sam_gui.counter)).pack(side=RIGHT)
    tmp.pack(expand=True, fill=BOTH)
    sam_gui.elems.append(tmp)
    sam_gui.counter += 1
    sam_gui.update()


def create_example_conf():
    example_config = {"sam_enabled": True, "sam_api_key": None,
                      "sam_types": [], "sam_naics": [], "grants_enabled": True, "grants_cats": [], "grants_eligibilities": [], "grants_instruments": []}

    for sol_type in sol_typ_abv_plain_map.keys():
        if random.choice([True, False]):
            example_config['sam_types'].append(sol_type)

    for e in grants_fund_instruments_abv_plain.keys():
        if random.choice([True, False]):
            example_config['grants_instruments'].append(e)

    for e in grants_eligibilities_abv_plain.keys():
        if random.choice([True, False]):
            example_config['grants_eligibilities'].append(e)

    for e in grants_cats_abv_plain.keys():
        if random.choice([True, False]):
            example_config['grants_cats'].append(e)

    with open(conf_path, 'w') as f:
        json.dump(example_config, f, indent=4)


# This is the most important method. before anything even starts, we check config
# and try and fix as many problems as we can so we don't have to bug the user.
# i.e. bad config, missing config, etc.
# this is what sets everything up for success
def cfg_bootstrap():
    # grants_enabled, sam_enabled -- whether these things are configured or not
    # which will control whether we show the buttons to access them
    made_change = False

    if not os.path.exists(conf_path):
        create_example_conf()

    with open(conf_path, 'r') as file:
        config_data = file.read()

    if len(config_data) == 0:
        # just incase someone deletes everything in the file, rather than deleting the file itself
        # ok then, write an example one and read it right back in >_>
        create_example_conf()
        with open(conf_path, 'r') as file:
            config_data = file.read()

    config_json = None
    try:
        config_json = json.loads(config_data)
    except ValueError:
        YellAtSomeoneAndQuit("Error", "Bad config. Not valid JSON")

    ge, se = False, False
    if "sam_enabled" in config_json and config_json["sam_enabled"]:
        se = True
        if not all(ele in config_json for ele in cfg_sam_keys):
            YellAtSomeoneAndQuit("Error", "Missing config entry")

        # lazy length check for a proper API key
        if not ("sam_api_key" in config_json and not (config_json["sam_api_key"] is None)) or len(config_json["sam_api_key"]) != 40:
            gi = GetInputOrDie(msg="Please enter your SAM API Key", instructions="If you only want to use grants.gov, leave this blank and hit 'ok'.\n"
                                                                                 "If you wish to re-enabled this feature in the future, you'll have to\n"
                                                                                 "modify the configuration file located with this program to 'sam_enabled':True\n"
                                                                                 "Otherwise, to use sam.gov...\n\n"
                                                                                 "1. Visit https://beta.sam.gov\n"
                                                                                 "2. Create an account\n"
                                                                                 "3. Login to your account\n"
                                                                                 "4. Go to your profile page\n"
                                                                                 "5. Click the eye button reveal your Public API Key\n"
                                                                                 "6. Enter the one time code sent to your email address to reveal the code\n"
                                                                                 "7. (Recommended) Make sure your account is associated with an entity (your employer)\n"
                                                                                 "8. (Recommended) Under 'My Roles', pick whatever roles & domains are available\n"
                                                                                 "Note: This key expires every 90 days")
            gi.mainloop()
            apikey = gi.value
            if len(apikey) == 0:
                config_json["sam_enabled"] = False
                se = False
            elif len(apikey) == 40:
                config_json["sam_api_key"] = apikey
                config_json["sam_api_key_last_change"] = today
            else:
                YellAtSomeoneAndQuit("Error", "The API key wasn't empty, and wasn't the proper length")
                return

        else:
            # else, if they do have the API key set, then lets check the last changed date
            # and alert the user if its about to expire
            if bug_user_about_expired_key:
                if "sam_api_key_last_change" in config_json:
                    try:
                        lc_dt = datetime.strptime(config_json["sam_api_key_last_change"], '%m/%d/%Y')
                        diff = today_dt - lc_dt
                        if diff.days > (key_expiry_days - 7):  # aka only 1 week left at most
                            days_left = key_expiry_days - diff.days
                            if days_left < 0:
                                days_left = 0

                            root = Tk()
                            root.withdraw()
                            res = messagebox.askyesno("Your API key may be about to expire", "Your sam.gov API key may be about to expire in "
                                                      + str(days_left) + " days. Do you want to enter in a new one?")
                            root.destroy()

                            if res:
                                giod = GetInputOrDie(msg="Your API key may be about to expire", instructions="Please enter your new API key")
                                giod.mainloop()
                                apikey = giod.value
                                config_json["sam_api_key"] = apikey
                                config_json["sam_api_key_last_change"] = today

                    except ValueError:  # if its badly formatted, just put todays date
                        config_json["sam_api_key_last_change"] = today
                        made_change = True
                else:  # if this field doesn't exist, create it
                    config_json["sam_api_key_last_change"] = today
                    made_change = True

        for idx in range(len(config_json["sam_naics"])):
            if not isinstance(config_json["sam_naics"][idx], (int, dict)):
                YellAtSomeoneAndQuit("Error",
                                     "Invalid NAICS code. Only a number without quotes is allowed, or an object like: "
                                     "{\"desc\":\"The Description\",\"code\":1234}\n\nBad entry, #" + str(
                                         idx) + " : " + str(config_json["sam_naics"][idx]))

            if isinstance(config_json["sam_naics"][idx], int):
                made_change = True
                desc = get_naics_description(config_json["sam_naics"][idx])
                config_json["sam_naics"][idx] = {'code': config_json["sam_naics"][idx], 'desc': desc}

    if "grants_enabled" in config_json and config_json["grants_enabled"]:
        ge = True
        if "grants_instruments" not in config_json:
            made_change = True
            config_json["grants_instruments"] = []
        if "grants_cats" not in config_json:
            made_change = True
            config_json["grants_cats"] = []
        if "grants_eligibilities" not in config_json:
            made_change = True
            config_json["grants_eligibilities"] = []

    if made_change:
        write_new_config(config_json)

    if not se and not ge:
        YellAtSomeoneAndQuit("Error", "You must configure at least one opportunities source")

    global cfg
    cfg = config_json

    return se, ge


"""
###############################################################
99% of GUI related stuff is below this line
"""


# the simplest way without doing some complex gui/TCL navigation to
# see which side has more NAICS entrys on the SAM GUI window
# so that when we add one, we prefer the side w/ fewer entries
def how_many_children(parent):
    _list = parent.winfo_children()

    for item in _list:
        if item.winfo_children():
            _list.extend(item.winfo_children())

    return len(_list)


# This will center a draw window horizontally & vertically on the primary monitor
def center(win):
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height // 2)
    win.geometry('{}x{}+{}+{}'.format(width, height, x, y))


# Spawn a window to yell at someone about something
def yell_at_someone(msg_type, msg):
    error_root = Tk()
    error_root.title(msg_type)
    error_root.geometry("480x320")

    # create the widgets for the top part of the GUI, and lay them out
    Label(error_root, text=msg_type).pack(fill=BOTH, expand=True, padx=20, pady=10)
    Label(error_root, text=msg, wraplength=375).pack(fill=BOTH, expand=True, padx=20, pady=10)
    Button(error_root, text="Ok", command=lambda: error_root.destroy()).pack(fill=BOTH, expand=True, padx=20, pady=10)

    center(error_root)
    error_root.after(1, lambda: error_root.focus_force())  # for some reason, we don't get focus after spawning another window so we force it
    error_root.mainloop()


# Used to spawn a window when a fatal error occurs, which forces
# the program to quit once "exit" or the "x" is clicked
# Due to some issue w/ Macs, this should not be called if another window already exists
# use messagebox.showerror() & bye_global() instead
class YellAtSomeoneAndQuit(Tk):
    def __init__(self, msg_type, msg):
        super().__init__()
        self.title(msg_type)
        self.geometry("480x320")
        self.protocol('WM_DELETE_WINDOW', self.bye)

        # create the widgets for the top part of the GUI, and lay them out
        Label(self, text=msg_type).pack(fill=BOTH, expand=True, padx=20, pady=10)
        Label(self, text=msg, wraplength=375).pack(fill=BOTH, expand=True, padx=20, pady=10)
        Button(self, text="Exit", command=self.bye).pack(fill=BOTH, expand=True, padx=20, pady=10)

        center(self)
        self.after(1, lambda: self.focus_force())  # for some reason, we don't get focus after spawning another window so we force it
        self.mainloop()

    def bye(self):
        self.destroy()
        bye_global()


# Used when input is required to proceed (just the SAM API key at this point)
# either the user provides input, or clicks "x" / "exit" which quits the program
# as we cannot proceed further unless the user complies
class GetInputOrDie(Tk):
    def __init__(self, msg="Input", instructions=None):
        super().__init__()
        self.title(msg)
        self.protocol('WM_DELETE_WINDOW', self.bye)

        Label(self, text=msg).pack()
        if instructions:
            Label(self, text=instructions, justify=LEFT).pack(fill=BOTH, padx=20, pady=15)

        self.e = Entry(self, width=50)
        self.e.pack(pady=20)

        bottom = Frame(self)
        bottom.pack(side=BOTTOM)
        Button(self, text='Exit', command=self.bye, width=10).pack(in_=bottom, side=RIGHT, padx=10, pady=10)
        Button(self, text='Ok', command=self.cleanup, width=10).pack(in_=bottom, side=RIGHT, padx=10, pady=10)
        self.value = None
        center(self)
        self.after(1, lambda: self.focus_force())  # for some reason, we don't get focus after spawning another window so we force it

    def bye(self):
        self.destroy()
        bye_global()

    def cleanup(self):
        self.value = self.e.get()
        self.destroy()


# This spawns the main grants.gov window
class GrantsConfigure(Tk):
    def __init__(self):
        super().__init__()
        self.title("grants.gov collector")
        self.protocol('WM_DELETE_WINDOW', self.bye)

        # create the main sections of the layout
        self.fund_instruments = Frame(self)
        self.eligibilities1 = Frame(self)
        self.eligibilities2 = Frame(self)
        self.cats1 = Frame(self)
        self.cats2 = Frame(self)
        self.cats3 = Frame(self)
        self.cats4 = Frame(self)
        self.cats5 = Frame(self)
        self.cats6 = Frame(self)
        self.dates = Frame(self)
        self.bottom = Frame(self)

        self.fund_instruments.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        self.eligibilities1.pack(side=TOP)
        self.eligibilities2.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        self.cats1.pack(side=TOP)
        self.cats2.pack(side=TOP)
        self.cats3.pack(side=TOP)
        self.cats4.pack(side=TOP)
        self.cats5.pack(side=TOP)
        self.cats6.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        self.dates.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        self.bottom.pack(side=BOTTOM, fill=BOTH, expand=True)

        '''############ INSTRUMENT TYPES ####################'''
        Label(self, text="Instrument Types").pack(in_=self.fund_instruments, side=TOP)

        self.inst_G = Checkbutton(self, text=grants_fund_instruments_abv_plain["G"], command=partial(toggle_grants_inst, "G"))
        self.inst_G.pack(in_=self.fund_instruments, side=LEFT)
        if "G" in cfg['grants_instruments']:
            self.inst_G.select()

        self.inst_CA = Checkbutton(self, text=grants_fund_instruments_abv_plain["CA"], command=partial(toggle_grants_inst, "CA"))
        self.inst_CA.pack(in_=self.fund_instruments, side=LEFT)
        if "CA" in cfg['grants_instruments']:
            self.inst_CA.select()

        self.inst_O = Checkbutton(self, text=grants_fund_instruments_abv_plain["O"], command=partial(toggle_grants_inst, "O"))
        self.inst_O.pack(in_=self.fund_instruments, side=LEFT)
        if "O" in cfg['grants_instruments']:
            self.inst_O.select()

        self.inst_PC = Checkbutton(self, text=grants_fund_instruments_abv_plain["PC"], command=partial(toggle_grants_inst, "PC"))
        self.inst_PC.pack(in_=self.fund_instruments, side=LEFT)
        if "PC" in cfg['grants_instruments']:
            self.inst_PC.select()

        '''############ ELIGIBILITIES ####################'''
        Label(self, text="Eligibilities").pack(in_=self.eligibilities1, side=TOP)

        self.elig_99 = Checkbutton(self, text=grants_eligibilities_abv_plain["99"], command=partial(toggle_grants_elig, "99"))
        self.elig_99.pack(in_=self.eligibilities1, side=LEFT)
        if "99" in cfg['grants_eligibilities']:
            self.elig_99.select()

        self.elig_12 = Checkbutton(self, text=grants_eligibilities_abv_plain["12"], command=partial(toggle_grants_elig, "12"))
        self.elig_12.pack(in_=self.eligibilities1, side=LEFT)
        if "12" in cfg['grants_eligibilities']:
            self.elig_12.select()

        self.elig_13 = Checkbutton(self, text=grants_eligibilities_abv_plain["13"], command=partial(toggle_grants_elig, "13"))
        self.elig_13.pack(in_=self.eligibilities1, side=LEFT)
        if "13" in cfg['grants_eligibilities']:
            self.elig_13.select()

        self.elig_20 = Checkbutton(self, text=grants_eligibilities_abv_plain["20"], command=partial(toggle_grants_elig, "20"))
        self.elig_20.pack(in_=self.eligibilities1, side=LEFT)
        if "20" in cfg['grants_eligibilities']:
            self.elig_20.select()

        self.elig_21 = Checkbutton(self, text=grants_eligibilities_abv_plain["21"], command=partial(toggle_grants_elig, "21"))
        self.elig_21.pack(in_=self.eligibilities2, side=LEFT)
        if "21" in cfg['grants_eligibilities']:
            self.elig_21.select()

        self.elig_22 = Checkbutton(self, text=grants_eligibilities_abv_plain["22"], command=partial(toggle_grants_elig, "22"))
        self.elig_22.pack(in_=self.eligibilities2, side=LEFT)
        if "22" in cfg['grants_eligibilities']:
            self.elig_22.select()

        self.elig_23 = Checkbutton(self, text=grants_eligibilities_abv_plain["23"], command=partial(toggle_grants_elig, "23"))
        self.elig_23.pack(in_=self.eligibilities2, side=LEFT)
        if "23" in cfg['grants_eligibilities']:
            self.elig_23.select()

        self.elig_25 = Checkbutton(self, text=grants_eligibilities_abv_plain["25"], command=partial(toggle_grants_elig, "25"))
        self.elig_25.pack(in_=self.eligibilities2, side=LEFT)
        if "25" in cfg['grants_eligibilities']:
            self.elig_25.select()

        '''############ CATS ####################'''
        Label(self, text="Categories").pack(in_=self.cats1, side=TOP)

        self.cat_BC = Checkbutton(self, text=grants_cats_abv_plain["BC"], command=partial(toggle_grants_cat, "BC"))
        self.cat_BC.pack(in_=self.cats1, side=LEFT)
        if "BC" in cfg['grants_cats']:
            self.cat_BC.select()

        self.cat_CD = Checkbutton(self, text=grants_cats_abv_plain["CD"], command=partial(toggle_grants_cat, "CD"))
        self.cat_CD.pack(in_=self.cats1, side=LEFT)
        if "CD" in cfg['grants_cats']:
            self.cat_CD.select()

        self.cat_CP = Checkbutton(self, text=grants_cats_abv_plain["CP"], command=partial(toggle_grants_cat, "CP"))
        self.cat_CP.pack(in_=self.cats1, side=LEFT)
        if "CP" in cfg['grants_cats']:
            self.cat_CP.select()

        self.cat_DPR = Checkbutton(self, text=grants_cats_abv_plain["DPR"], command=partial(toggle_grants_cat, "DPR"))
        self.cat_DPR.pack(in_=self.cats1, side=LEFT)
        if "DPR" in cfg['grants_cats']:
            self.cat_DPR.select()

        # Second row
        self.cat_ED = Checkbutton(self, text=grants_cats_abv_plain["ED"], command=partial(toggle_grants_cat, "ED"))
        self.cat_ED.pack(in_=self.cats2, side=LEFT)
        if "ED" in cfg['grants_cats']:
            self.cat_ED.select()

        self.cat_ELT = Checkbutton(self, text=grants_cats_abv_plain["ELT"], command=partial(toggle_grants_cat, "ELT"))
        self.cat_ELT.pack(in_=self.cats2, side=LEFT)
        if "ELT" in cfg['grants_cats']:
            self.cat_ELT.select()

        self.cat_EN = Checkbutton(self, text=grants_cats_abv_plain["EN"], command=partial(toggle_grants_cat, "EN"))
        self.cat_EN.pack(in_=self.cats2, side=LEFT)
        if "EN" in cfg['grants_cats']:
            self.cat_EN.select()

        self.cat_ENV = Checkbutton(self, text=grants_cats_abv_plain["ENV"], command=partial(toggle_grants_cat, "ENV"))
        self.cat_ENV.pack(in_=self.cats2, side=LEFT)
        if "ENV" in cfg['grants_cats']:
            self.cat_ENV.select()

        self.cat_HL = Checkbutton(self, text=grants_cats_abv_plain["HL"], command=partial(toggle_grants_cat, "HL"))
        self.cat_HL.pack(in_=self.cats2, side=LEFT)
        if "HL" in cfg['grants_cats']:
            self.cat_HL.select()

        # Third row
        self.cat_HU = Checkbutton(self, text=grants_cats_abv_plain["HU"], command=partial(toggle_grants_cat, "HU"))
        self.cat_HU.pack(in_=self.cats3, side=LEFT)
        if "HU" in cfg['grants_cats']:
            self.cat_HU.select()

        self.cat_IS = Checkbutton(self, text=grants_cats_abv_plain["IS"], command=partial(toggle_grants_cat, "IS"))
        self.cat_IS.pack(in_=self.cats3, side=LEFT)
        if "IS" in cfg['grants_cats']:
            self.cat_IS.select()

        self.cat_LJL = Checkbutton(self, text=grants_cats_abv_plain["LJL"], command=partial(toggle_grants_cat, "LJL"))
        self.cat_LJL.pack(in_=self.cats3, side=LEFT)
        if "LJL" in cfg['grants_cats']:
            self.cat_LJL.select()

        self.cat_NR = Checkbutton(self, text=grants_cats_abv_plain["NR"], command=partial(toggle_grants_cat, "NR"))
        self.cat_NR.pack(in_=self.cats3, side=LEFT)
        if "NR" in cfg['grants_cats']:
            self.cat_NR.select()

        # Fourth row
        self.cat_RA = Checkbutton(self, text=grants_cats_abv_plain["RA"], command=partial(toggle_grants_cat, "RA"))
        self.cat_RA.pack(in_=self.cats4, side=LEFT)
        if "RA" in cfg['grants_cats']:
            self.cat_RA.select()

        self.cat_RD = Checkbutton(self, text=grants_cats_abv_plain["RD"], command=partial(toggle_grants_cat, "RD"))
        self.cat_RD.pack(in_=self.cats4, side=LEFT)
        if "RD" in cfg['grants_cats']:
            self.cat_RD.select()

        self.cat_ST = Checkbutton(self, text=grants_cats_abv_plain["ST"], command=partial(toggle_grants_cat, "ST"))
        self.cat_ST.pack(in_=self.cats4, side=LEFT)
        if "ST" in cfg['grants_cats']:
            self.cat_ST.select()

        self.cat_T = Checkbutton(self, text=grants_cats_abv_plain["T"], command=partial(toggle_grants_cat, "T"))
        self.cat_T.pack(in_=self.cats4, side=LEFT)
        if "T" in cfg['grants_cats']:
            self.cat_T.select()

        # Fifth row
        self.cat_O = Checkbutton(self, text=grants_cats_abv_plain["O"], command=partial(toggle_grants_cat, "O"))
        self.cat_O.pack(in_=self.cats5, side=LEFT)
        if "O" in cfg['grants_cats']:
            self.cat_O.select()

        self.cat_ACA = Checkbutton(self, text=grants_cats_abv_plain["ACA"], command=partial(toggle_grants_cat, "ACA"))
        self.cat_ACA.pack(in_=self.cats5, side=LEFT)
        if "ACA" in cfg['grants_cats']:
            self.cat_ACA.select()

        self.cat_AG = Checkbutton(self, text=grants_cats_abv_plain["AG"], command=partial(toggle_grants_cat, "AG"))
        self.cat_AG.pack(in_=self.cats5, side=LEFT)
        if "AG" in cfg['grants_cats']:
            self.cat_AG.select()

        self.cat_AR = Checkbutton(self, text=grants_cats_abv_plain["AR"], command=partial(toggle_grants_cat, "AR"))
        self.cat_AR.pack(in_=self.cats5, side=LEFT)
        if "AR" in cfg['grants_cats']:
            self.cat_AR.select()

        # Sixth row :(
        self.cat_FN = Checkbutton(self, text=grants_cats_abv_plain["FN"], command=partial(toggle_grants_cat, "FN"))
        self.cat_FN.pack(in_=self.cats6, side=LEFT)
        if "FN" in cfg['grants_cats']:
            self.cat_FN.select()

        self.cat_HO = Checkbutton(self, text=grants_cats_abv_plain["HO"], command=partial(toggle_grants_cat, "HO"))
        self.cat_HO.pack(in_=self.cats6, side=LEFT)
        if "HO" in cfg['grants_cats']:
            self.cat_HO.select()

        self.cat_ISS = Checkbutton(self, text=grants_cats_abv_plain["ISS"], command=partial(toggle_grants_cat, "ISS"))
        self.cat_ISS.pack(in_=self.cats6, side=LEFT)
        if "ISS" in cfg['grants_cats']:
            self.cat_ISS.select()

        '''############ Date ####################'''
        Label(self, text="How many previous days worth").pack(in_=self.dates, side=TOP)
        self.past_days = Entry()
        self.past_days.pack(in_=self.dates, side=TOP)
        self.past_days.insert(0, "30")

        '''############ BOTTOM BUTTONS ####################'''
        Button(self, text="Exit", width=10, height=2, command=self.bye).pack(in_=self.bottom, side=RIGHT, padx=10, pady=10)
        self.get_button = Button(self, text="Get", width=10, height=2, command=self.get_data)
        self.get_button.pack(in_=self.bottom, side=RIGHT, padx=10, pady=10)

        center(self)  # center x&y on monitor
        self.after(1, lambda: self.focus_force())  # for some reason, we don't get focus after spawning another window so we force it

    def bye(self):
        self.destroy()
        bye_global()

    def get_data(self):
        self.get_button["state"] = "disabled"
        get_grants()


class SamConfigure(Tk):
    def __init__(self):
        super().__init__()
        self.title("sam.gov collector")
        self.protocol('WM_DELETE_WINDOW', self.bye)
        # self.geometry("800x640")

        # create the main sections of the layout, and lay them out
        self.top1 = Frame(self)
        self.top2 = Frame(self)

        self.naics_codes_holder = Frame(self)
        self.naics_left = Frame(self.naics_codes_holder)
        self.naics_right = Frame(self.naics_codes_holder)
        self.naics_add_holder = Frame(self)

        self.output = Frame(self)

        self.dates = Frame(self)
        self.date_from = Frame(self.dates)
        self.date_to = Frame(self.dates)

        self.bottom = Frame(self)

        self.top1.pack(side=TOP)
        self.top2.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        Label(self, text="NAICS Codes").pack(in_=self, side=TOP)
        self.naics_codes_holder.pack(side=TOP, pady=20)
        self.naics_left.pack(side=LEFT, padx=20)
        self.naics_right.pack(side=RIGHT, padx=20)
        self.naics_add_holder.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        Label(self, text="Date Range").pack(in_=self, side=TOP)
        self.dates.pack(side=TOP)
        self.date_from.pack(side=LEFT, padx=20)
        self.date_to.pack(side=RIGHT, padx=20)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        self.output.pack(side=TOP)
        Frame(self, height=1, width=50, bg="black").pack(fill=BOTH, padx=20, pady=20)  # aka <hr>
        self.bottom.pack(side=BOTTOM, fill=BOTH, expand=True)

        # u = Justification (J&A), p = Pre solicitation, a = Award Notice
        # r = Sources Sought, s = Special Notice, g = Sale of Surplus Property
        # k = Combined Synopsis/Solicitation, i = Intent to Bundle Requirements (DoD-Funded)
        # This is the top part where u select what types
        Label(self, text="Opportunity Types").pack(in_=self.top1, side=TOP)

        self.sam_u = Checkbutton(self, text="Justification (J&A)", command=partial(toggle_sam_sol_type, "u"))
        self.sam_u.pack(in_=self.top1, side=LEFT)
        if "u" in cfg['sam_types']:
            self.sam_u.select()

        self.sam_p = Checkbutton(self, text="Pre solicitation", command=partial(toggle_sam_sol_type, "p"))
        self.sam_p.pack(in_=self.top1, side=LEFT)
        if "p" in cfg['sam_types']:
            self.sam_p.select()

        self.sam_a = Checkbutton(self, text="Award Notice", command=partial(toggle_sam_sol_type, "a"))
        self.sam_a.pack(in_=self.top1, side=LEFT)
        if "a" in cfg['sam_types']:
            self.sam_a.select()

        self.sam_r = Checkbutton(self, text="Sources Sought", command=partial(toggle_sam_sol_type, "r"))
        self.sam_r.pack(in_=self.top1, side=LEFT)
        if "r" in cfg['sam_types']:
            self.sam_r.select()

        self.sam_o = Checkbutton(self, text="Solicitation", command=partial(toggle_sam_sol_type, "o"))
        self.sam_o.pack(in_=self.top1, side=LEFT)
        if "o" in cfg['sam_types']:
            self.sam_o.select()

        self.sam_s = Checkbutton(self, text="Special Notice", command=partial(toggle_sam_sol_type, "s"))
        self.sam_s.pack(in_=self.top2, side=LEFT)
        if "s" in cfg['sam_types']:
            self.sam_s.select()

        self.sam_i = Checkbutton(self, text="Intent To Bundle Reqs.", command=partial(toggle_sam_sol_type, "i"))
        self.sam_i.pack(in_=self.top2, side=LEFT)
        if "i" in cfg['sam_types']:
            self.sam_i.select()

        self.sam_g = Checkbutton(self, text="Sale of Surplus Property", command=partial(toggle_sam_sol_type, "g"))
        self.sam_g.pack(in_=self.top2, side=LEFT)
        if "g" in cfg['sam_types']:
            self.sam_g.select()

        self.sam_k = Checkbutton(self, text="Combined Synopsis/Solicitation", command=partial(toggle_sam_sol_type, "k"))
        self.sam_k.pack(in_=self.top2, side=LEFT)
        if "k" in cfg['sam_types']:
            self.sam_k.select()

        # NAICS stuffs
        self.counter = 0
        self.elems = []
        for code in cfg['sam_naics']:
            txt = str(code['code'])
            if code['desc']:
                txt = txt + " - " + code['desc']
            else:
                txt = txt + " - " + "N/A"

            if self.counter % 2 == 0:
                tmp = Frame(self.naics_left)
            else:
                tmp = Frame(self.naics_right)

            Label(tmp, text=txt).pack(side=LEFT)
            Button(tmp, text="Remove", width=10, command=partial(remove_sam_naics, code['code'], self.counter)).pack(side=RIGHT)
            tmp.pack(expand=True, fill=BOTH)
            self.elems.append(tmp)
            self.counter += 1

        # Add new NAICS code
        self.naics_entry = Entry()
        self.naics_entry.pack(in_=self.naics_add_holder, side=LEFT)
        Button(self, text="Add NAICS", width=10, command=add_sam_naics).pack(in_=self.naics_add_holder, side=RIGHT, padx=10)

        # Date picker section
        from_date = get_latest_csv("__sam")
        if not from_date:
            from_date = (datetime.now() - timedelta(30)).strftime('%m/%d/%Y')
        Label(text="From Date").pack(in_=self.date_from, side=LEFT)
        self.from_date_e = Entry()
        self.from_date_e = Entry()
        self.from_date_e.pack(in_=self.date_from, side=LEFT)
        self.from_date_e.insert(0, from_date)

        Label(text="To Date").pack(in_=self.date_to, side=LEFT)
        self.to_date_e = Entry()
        self.to_date_e.pack(in_=self.date_to, side=LEFT)
        self.to_date_e.insert(0, datetime.now().strftime('%m/%d/%Y'))

        # text output section
        self.text = Text(self, height=4)
        scrollbar = Scrollbar(self)
        scrollbar.config(command=self.text.yview)
        self.text.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(in_=self.output, side=RIGHT, fill=Y)
        self.text.pack(in_=self.output, side=LEFT, fill=BOTH, expand=True)

        # bottom buttons
        Button(self, text="Exit", width=10, height=2, command=self.bye).pack(in_=self.bottom, side=RIGHT, padx=10, pady=10)
        self.get_button = Button(self, text="Get", width=10, height=2, command=self.get_data_thread)
        self.get_button.pack(in_=self.bottom, side=RIGHT, padx=10, pady=10)

        center(self)  # center x&y on monitor
        self.after(1, lambda: self.focus_force())  # for some reason, we don't get focus after spawning another window so we force it

    def add_log(self, msg, mtype="INFO: "):
        self.text.configure(state='normal')
        self.text.insert(END, mtype + msg + '\n')
        self.text.configure(state='disabled')
        # Autoscroll to the bottom
        self.text.yview(END)
        self.update_idletasks()

    def bye(self):
        self.destroy()
        bye_global()

    def get_data_thread(self):
        self.get_button["state"] = "disabled"
        t = threading.Thread(target=get_sam_opps, daemon=True)
        t.start()


class MainGui(Tk):
    def __init__(self, sam_enabled=False, grants_enabled=False):
        super().__init__()
        self.title("Choose Source")
        self.geometry("480x320")
        self.protocol('WM_DELETE_WINDOW', self.bye)  # root is your root window
        self.sam_enabled = sam_enabled
        self.grants_enabled = grants_enabled

        # we've already checked in cfg_bootstrap that at least one of these is enabled
        # create the widgets for the top part of the GUI, and lay them out

        # can't change the size of buttons on macOs :/, so these are labels now
        # https://stackoverflow.com/questions/25951262/how-to-adjust-tkinter-button-height
        if sam_enabled:
            # Button(self, relief=GROOVE, text="Sam.gov", command=self.on_sam).pack(fill=BOTH, expand=True, padx=20, pady=10)
            sl = Label(self, relief=GROOVE, text="Sam.gov")
            sl.bind("<Button>", self.on_sam)
            sl.pack(fill=BOTH, expand=True, padx=20, pady=10)

        if grants_enabled:
            gl = Label(self, relief=GROOVE, text="Grants.gov")
            gl.bind("<Button>", self.on_grants)
            gl.pack(fill=BOTH, expand=True, padx=20, pady=10)

        center(self)
        self.after(1, lambda: self.focus_force())  # for some reason, we don't get focus after spawning another window so we force it

    def on_sam(self, e):
        self.destroy()
        global sam_gui
        sam_gui = SamConfigure()
        sam_gui.mainloop()

    def on_grants(self, e):
        self.destroy()
        global grants_gui
        grants_gui = GrantsConfigure()
        grants_gui.mainloop()

    def bye(self):
        self.destroy()
        bye_global()


if __name__ == "__main__":
    sam_e, grants_e = cfg_bootstrap()
    main_gui = MainGui(sam_enabled=sam_e, grants_enabled=grants_e)
    main_gui.mainloop()
