# author: jf

import datetime
import getpass
from sys import platform

import requests

# {"eligibilities":"20|21|23|99|06","fundingCategories":"BC|CD|EN|IS|LJL|ST|T","startRecordNum":0,"oppStatuses":"forecasted|posted","sortBy":"openDate|desc"}

if __name__ == "__main__":

    print("Starting collecting of grants.gov ... ")

    user = getpass.getuser()
    if platform == "win32":
        output_dir = "c:\\users\\" + user + "\\desktop\\grants-gov_" + datetime.datetime.now().strftime("%Y-%m-%d") + ".csv"
    else:
        output_dir = "/home/" + user + "/grants-gov_" + datetime.datetime.now().strftime("%Y-%m-%d") + ".csv"

    url = "https://www.grants.gov/grantsws/rest/opportunities/search/csv/download?osjp={%22eligibilities%22:%2220|21|23|99|06%22,%22fundingCategories%22:%22BC|CD|EN|IS|LJL|ST|T%22,%22startRecordNum%22:0,%22oppStatuses%22:%22forecasted|posted%22,%22sortBy%22:%22openDate|desc%22,%22rows%22:9999}"

    r = requests.get(url)

    out = open(output_dir, "w")
    out.write(r.text.encode("utf-8"))
    out.close()

    input("Done! Press any key to exit")
