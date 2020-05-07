# author: jf

import csv
import getpass
import json
import time
from datetime import datetime, timedelta
from sys import platform

import requests

################ SETTINGS ###############
diff_from_last_request = True
range_days = 30  # how many days in the past to look. max 365
api_key = ""  # only valid for 90 days :(

# p=presolicitation;  k = Combined Synopsis/Solicitation; r = Sources Sought
ptypes = ["p", "r", "k"]

# the NAICS codes
ncodes = [511210, 5182, 518210, 519130, 519190, 5415, 541511, 541512, 541513, 541519, 541611, 541690, 541715, 541990]

############### dont touch me ##############################
start_date = (datetime.now() - timedelta(range_days)).strftime('%m/%d/%Y')
today = datetime.now().strftime('%m/%d/%Y')
endpoint = "https://api.sam.gov/prod/opportunities/v1/search"
filename = start_date.replace("/", "-") + "__" + today.replace("/", "-") + "__opps.csv"
user = getpass.getuser()
if platform == "win32":
    output_path = "C:\\users\\" + user + "\\desktop\\" + filename
else:
    output_path = "/home/" + user + "/" + filename
#############################################


opps = []
for ptype in ptypes:
    for ncode in ncodes:
        r = requests.get(endpoint, params={'api_key': api_key, 'limit': 1000, 'postedFrom': start_date,
                                           'postedTo': today, "ptype": ptype, "ncode": ncode})
        data = json.loads(r.text)
        if "error" in data:
            print("Error: " + data['error']['code'])
            print(r.headers)
            quit(1)

        if "opportunitiesData" in data:
            opps.extend(data["opportunitiesData"])
            print("Found " + str(len(data['opportunitiesData'])) + " for NAICS: " + str(ncode) + " solicitation type: " + ptype)
        else:
            print("No results for NAICS: " + str(ncode) + " solicitation type: " + ptype)

        time.sleep(5)

set_of_jsons = {json.dumps(d, sort_keys=True) for d in opps}
opps = [json.loads(t) for t in set_of_jsons]

keys = opps[0].keys()
with open(output_path, 'w', newline='') as output_file:
    dict_writer = csv.DictWriter(output_file, keys)
    dict_writer.writeheader()
    dict_writer.writerows(opps)
