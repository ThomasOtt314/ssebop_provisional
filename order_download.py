#!/usr/bin/env python
# coding: utf-8
# Import packages
import requests
import tarfile
import time
import os
import pandas as pd
from argparse import ArgumentParser
import logging
from configparser import ConfigParser
import rasterio

# Set up argparse for ini path
parser = ArgumentParser(description="Path to ini file")
parser.add_argument("-ini", type=str, help="Path to ini file")
args = parser.parse_args()
ini_path = str(args.ini)

# Set up config parser to read in .ini file
config = ConfigParser()
config.read(ini_path)

# Setup logging file
proj_directory = config["PROJECT_DIRECTORY"]["project_directory"]
log_name = "order_download.log"
logging.basicConfig(filename=os.path.join(proj_directory, log_name), level=logging.INFO,
                    format='%(levelname)s:%(message)s')

# define new model run
logging.info("  ")
logging.info(f"New Download for {config['ORDER_ID']['order_id']}")

# Change directory to temp directory
try:
    os.chdir("tmp_dir")
except Exception as e:
    print(e)
    exit()

# Get csv of urls for given station and convert them to a list
order_id_list = config["ORDER_ID"]["order_id"].replace(" ", "").split(",")

for order_id in order_id_list:
    logging.info(f"Starting download for order_id: {order_id}")
    file_path = os.path.join(f"..\{config['PROJECT_DIRECTORY']['project_directory']}", f"{order_id}.csv")
    try:
        url_list = list(pd.read_csv(file_path).loc[:,"0"])
    except FileNotFoundError as e:
        print(f"File {file_path} was not found")
        print(e)
        exit()
    except Exception as e:
        print(e)

    # Create metadata folder
    new_dir_path = os.path.join(f"..\{config['PROJECT_DIRECTORY']['project_directory']}", "meta_data")
    if os.path.exists(new_dir_path):
        pass
    else:
        os.mkdir(new_dir_path)

    # Loop through each image and download and extract
    start_time = time.time() # get start time of overall download time for logging purposes
    logging.info(f"Downloading started at {start_time}")
    x = 0 # set counter

    for url in url_list:
        start_time_2 = time.time() # get time for each process
        x+=1
        file_name = url.rsplit('/', 1)[1]
        try:
            r = requests.get(url)
        except Exception as e:
            print(e)
            exit()
        file = open(file_name, 'wb').write(r.content)
        # extract tiffs from file
        my_tar = tarfile.open(file_name)
        object_name = str(my_tar.getmembers()[0]).split("'")[1].rsplit("_", 2)[0]

        # Determine bands to keep, based on selected bands from ini file
        all_product = ['source_metadata', 'l1', 'toa', 'bt', 'sr', 'toa', 'pixel_qa', 'aq_refl', 'et', 'stats',
                       'sr_ndvi', 'sr_evi', 'sr_savi', 'sr_msavi', 'sr_ndmi', 'sr_nbr', 'sr_nbr2']
        # dictionaries for band extension for given product selection
        ls_57_prod_dic = {"bt": ["_bt_band6.tif"], "et": ["_etf.tif", "_eta.tif"], "pixel_qa":["_pixel_qa.tif"]}
        ls_8_prod_dic = {"bt": ["_bt_band10.tif","_bt_band11.tif" ], "et": ["_etf.tif", "_eta.tif"],
                         "pixel_qa" : ["_pixel_qa.tif"]}

        ls_prods = config["ORDER_VARIABLES"]["product_list"].replace(" ", "")\
                    .split(",")  # remove any extra spaces and parse into list
        # object_name example "LC08_L1TP_025033_20130401_20170310_01_T1"
        band_list_75 = None # prevents these lists from being undefined
        band_list_8 = None # prevents these lists from being undefined
        if (object_name[3] == "5") or (object_name[3] == "7"):
            band_list = [".xml"]
            for product in ls_prods:
                band_list += ls_57_prod_dic[product]
            band_list_75 = band_list # used for reference later
        elif object_name[3] == "8":
            band_list = [".xml"]
            for product in ls_prods:
                band_list += ls_8_prod_dic[product]
            band_list_8 = band_list # used for reference later
        else:
            print("error")
            print(file_name)
            os.remove(file_name)
            continue

        # Extract metadata band and move to meta data folder
        file_list = []  # stores bands used for band composite
        for p in band_list:
            if p == ".xml":
                meta_path = os.path.join(f"..\{config['PROJECT_DIRECTORY']['project_directory']}", "meta_data")
                my_tar.extract(f"{object_name}{p}", meta_path)
            else:
                my_tar.extract(object_name+p)
                file_list.append(object_name+p)
        my_tar.close()
        os.remove(file_name) # removes .tar.gz file from temp_dir
        # composite bands in file_list
        with rasterio.open(file_list[0]) as src0:
            meta = src0.meta

        # Update meta to reflect the number of layers
        meta.update(count = len(file_list))

        # Read each layer and write it to stack
        # all input layers must be of same extent, resolution, and data type
        with rasterio.open(object_name+'.tif', 'w', **meta) as dst:
            for id, layer in enumerate(file_list, start=1):
                with rasterio.open(layer) as src1:
                    dst.write_band(id, src1.read(1).astype(rasterio.int16))
        # removes files from file_list after compositing
        for tiff_file in file_list:
            os.remove(tiff_file)

        #upload images to cloud
        print("Begining upload to Cloud")
        cloud_id = config["STORAGE"]["cloud_id"]
        os.system(f'gsutil -m -o GSUtil:parallel_composite_upload_threshold=150M cp -R ./ {cloud_id}')

        os.remove(object_name+'.tif')
        print(x)
        print(f"{file_name} uploaded to cloud successfully")
        logging.info(f"{file_name} uploaded to cloud successfully")
        process_time_2 = (time.time() - start_time_2)
        print(f"Upload time: {process_time_2} sec")
        logging.info(f"Upload time: {process_time_2} sec")

    process_time =  (time.time() - start_time)
    print("")
    print("")
    print(f"Total images uploaded for order_id {order_id}: {x}")
    print(f"Total time for order_id {order_id}: {process_time}")

    print(f"Final composite layers for LS 5 or 7 will be in order as: {band_list_75}")
    print(f"Final composite layers for LS 8 will be in order as: {band_list_8}")
    logging.info(f"Final composite layers for LS 5 or 7 will be in order as: {band_list_75}")
    logging.info(f"Final composite layers for LS 8 will be in order as: {band_list_8}")

