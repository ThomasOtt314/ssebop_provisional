#!/usr/bin/env python
# coding: utf-8

import requests
import pandas as pd
from configparser import ConfigParser
import logging
import os.path
from argparse import ArgumentParser

#Set up argparse for ini path
parser = ArgumentParser(description="Path to ini file")
parser.add_argument("name", type=str, help="Path to ini file")
args = parser.parse_args()
ini_path = str(args.name)

#Set up config parser to read in .ini file
config = ConfigParser()
config.read(ini_path)

#setup logging file
proj_directory = config["PROJECT_DIRECTORY"]["project_directory"]
log_name = "order_status.log"
logging.basicConfig(filename=os.path.join(proj_directory, log_name), level=logging.INFO,
                    format='%(levelname)s:%(message)s')

#Set up ESPA accoundt user information
username = config["USER_ACCOUNT"]["username"]
password = config["USER_ACCOUNT"]["password"]
#Set host website
host = 'https://espa.cr.usgs.gov/api/v1/'

def espa_api(endpoint, verb='get', body=None, uauth=None):
    """ Suggested simple way to interact with the ESPA JSON REST API """
    auth_tup = uauth if uauth else (username, password)
    response = getattr(requests, verb)(host + endpoint, auth=auth_tup, json=body)
    #print('{} {}'.format(response.status_code, response.reason))
    data = response.json()
    if isinstance(data, dict):
        messages = data.pop("messages", None)  
        if messages:
            #print(json.dumps(messages, indent=4))
            return messages
    try:
        response.raise_for_status()
    except Exception as e:
        print(e)
    else:
        return data

#Test to confirm user account is active
print('Running test reuqest')
resp = espa_api('user')

if "warnings" in resp:
    print("ERROR: Test unsuccesful: Check username and password")
    exit()
elif resp["username"] == username:
    print("Test succesful")
else:
    print("ERROR: Unknown")
    exit()

order_id = config["ORDER_ID"]["order_id"].replace(" ", "").split(",")

for id in order_id:
    #define new model run
    logging.info(f"Status update for {id}")
    #Get overall order status
    resp = espa_api('order-status/{}'.format(id))
    if resp["status"] == 'complete':
        print("Order is complete: downloading url list")
        #extracting urls for complete images
        resp = espa_api('item-status/{0}'.format(id), body={'status': 'complete'})
        urls = []
        for item in resp[id]:
            urls.append(item.get('product_dload_url'))
        pd.DataFrame(urls).to_csv(f"{id}.csv", index=False)

        #Extract images that were  unavailable
        print("Images not downloaded due to C factor constraints: Check log for list")
        resp = espa_api('item-status/{0}'.format(id), body={'status': 'unavailable'})
        ids = []
        for item in resp[id]:
            ids.append(item.get('name'))
        logging.info("Unavailable image ids")
        logging.info(ids)

        print("done")
    elif resp["status"] == 'ordered':
        print("Order is still being processed")
        logging.info(f"Order {id} is still processing")


