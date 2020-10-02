#!/usr/bin/env python
# coding: utf-8

# In[4]:


import requests
import pandas as pd
from configparser import ConfigParser
import logging
import os
from argparse import ArgumentParser
import os.path
# import sys

# import numpy as np
# import json

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
log_name = "order_information.log"
logging.basicConfig(filename=os.path.join(proj_directory, log_name), level=logging.INFO,
                    format='%(levelname)s:%(message)s')

#define new model run
logging.info("  ")
logging.info("New order")

#Parse ESPA account info
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
    print("ERROR: Test unsuccessful: Check username and password")
    logging.info("ERROR: Test unsuccessful: Check username and password")
    exit()
elif resp["username"] == username:
    print("Test successful")
    logging.info("Test successful")
else:
    print("ERROR: Unknown")
    logging.info("ERROR: Test unsuccessful, unknown")
    exit()
###Set up order###
#Read in id list
id_list_path = os.path.join(proj_directory, config["ORDER_VARIABLES"]["id_list_path"])
try:
    ls = list(pd.read_csv(id_list_path, header=None)[0].unique())
except FileNotFoundError as e:
    print("File not Found: Check file path")
    print(e)
    exit()
except pd.errors.ParserError as e:
    print("ERROR: Make sure id_list_path file is a .csv")
    print(e)
    exit()
except Exception as e:
    print(e)
    exit()
#Test for list length, if greater than 10,000 won't accept
if len(ls) > 10000:
    print("ERROR: Landsat scene list is greater than 10,000. Can not process")
    exit()    
#Product list
all_product = ['source_metadata', 'l1', 'toa', 'bt', 'sr', 'toa', 'pixel_qa', 'aq_refl', 'et', 'stats',
               'sr_ndvi', 'sr_evi', 'sr_savi', 'sr_msavi','sr_ndmi', 'sr_nbr', 'sr_nbr2']

ls_prods = config["ORDER_VARIABLES"]["product_list"].replace(" ", "").split(",") #remove any extra spaces and parse into list
#test is requested products are available
for product in ls_prods:
    if product not in all_product:
        print(f"ERROR: Product {product} not availabe or, not formated incorrectly")
        exit()
##Separate into different zones##
def add_path_row(ls_id):
    '''Takes Landsat image id and returns the path row of image
    Requres id format LT05_L1TP_043034_20000116_20160919_01_T1'''
    pr = ls_id.rsplit("_")[2]
    return "p"+pr[0:3]+"r"+pr[3:]

def utm_zone(p_r):
    '''takes pqth row in p034r023 format and returns the UTM zone
    requres wrs2_zones dictionary to be defined'''
    return wrs2_zones[p_r]

def add_year(ls_id):
    '''Takes Landsat image id and returns the year of image
    Requres id format LT05_L1TP_043034_20000116_20160919_01_T1'''
    return ls_id.rsplit("_")[3][0:4]

#import dictionary of path_row and zone information
wrs2_zones = pd.read_csv('wrs2_zones.csv', index_col = 0).to_dict()["0"]
#create and add image id list to dataframe
id_df = pd.DataFrame()
id_df["id"] = ls
#add path_row, and zone to image id
id_df["path_row"] = id_df.loc[:,"id"].apply(add_path_row)
id_df["zone"] = id_df["path_row"].apply(utm_zone)

zone_id_dict = {}
for y in id_df["zone"].unique():
    export_df = list(id_df.loc[id_df["zone"] == y]["id"])
    if len(export_df) < 5000:
        zone_id_dict[str(y)+"a"] = export_df
    elif len(export_df) >= 5000:
        zone_id_dict[str(y)+"a"] = export_df[0:5000]
        zone_id_dict[str(y)+"b"] = export_df[5000:]
# blank list to store all order ids
order_id_list = []
order_id = None
for zone_str in zone_id_dict.keys():
    zone = int(zone_str[0:2])
    ls = zone_id_dict[zone_str]
    print(f"Ordering zone {zone_str}")
    logging.info(f"Ordering for zone {zone_str}")
    #Set order
    order = espa_api('available-products', body=dict(inputs=ls))
    
    #check order for restricted images
    if "date_restricted" in order.keys():
        restricted_dates = order['date_restricted']['aq_refl']
        ls = [i for i in ls if i not in restricted_dates]
        order = espa_api('available-products', body=dict(inputs=ls))
        logging.info("These ids were restricted and removed")
        logging.info(restricted_dates)
        print(f"Restricted dates encountered: {restricted_dates}")
        print("Restricted dates removed")
    else:
        logging.info("No restricted dates found")
        print("no restricted dates")
        #print(json.dumps(order, indent=4))
    
    # Replace the available products that was returned with what we want
    for sensor in order.keys():
        if isinstance(order[sensor], dict) and order[sensor].get('inputs'):
            order[sensor]['products'] = ls_prods
    
    # Add in the rest of the order information
    #set projection
    projection = {'utm': {'zone_ns': "north",
                          'zone': zone}}
    order['projection'] = projection
    order['format'] = config["ORDER_VARIABLES"]["order_format"]
    #order['resampling_method'] = 'cc'
    order['note'] = f"This order is for zone {zone_str}: {config['ORDER_VARIABLES']['note']}"
    
    #Check for non availabe images
    resp = espa_api('order', verb='post', body=order)
    #print(resp["errors"][0].keys())
    
    if "errors" in resp.keys():
        if 'Inputs Not Available' in resp["errors"][0].keys():
            non_dates = resp["errors"][0]["Inputs Not Available"]
            logging.info("These ids were not available:")
            logging.info(non_dates)
            print(f"Scene id's are not availalbe {non_dates}: removing")
            ls = [i for i in ls if i not in non_dates] #rests the image list
            order = espa_api('available-products', body=dict(inputs=ls)) #resubmits the order based on cleaned iamge list
            
            # Replace the available products that was returned with what we want
            for sensor in order.keys():
                if isinstance(order[sensor], dict) and order[sensor].get('inputs'):
                    order[sensor]['products'] = ls_prods
            # Add in the rest of the order information
            order['projection'] = projection
            order['format'] = config["ORDER_VARIABLES"]["order_format"]
            #order['resampling_method'] = 'cc'
            order['note'] = f"This order is for zone {zone_str}: {config['ORDER_VARIABLES']['note']}"

            #reorder
            resp = espa_api('order', verb='post', body=order)
            #print(resp)
            order_id = resp['orderid']
            print(f"Your ordier id is {order_id}")
            logging.info(f"Your order id is: {order_id}")

        else:
            print(f"ERROR: Something went wrong with order: {resp}")
    
    elif resp["status"] == "ordered":
        #print(resp)
        order_id = resp['orderid']
        print(f"Your ordier id is {order_id}")
        logging.info(f"Your order id is: {order_id}")


    else:
        print(f"ERROR: Something went wrong with order: {resp}")

    order_id_list.append(order_id)

config.set("ORDER_ID","order_id", str(order_id_list).strip("[]").replace("'", ""))
config.set
with open(ini_path, 'w') as configfile:    # save
    config.write(configfile)
print("done")
