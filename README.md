# ssebop_provisional_beta
This code is still in development state
#Instalation of packages

Use environment.yml to create conda environment for running
Will require instalation of google cloud storage on device and initiation in conda env. 
Once google cloud is installed on device run <gcloud init> in conand prompt of activated env.
You will also require and ESPA accound


###Setting up of project folder###
Inside main directory <provisional_ssebop> create new project folder. 
Folder will require an order.ini similar to one found in exmaple folder. 
Also required is image id csv in format of example_id_list.csv in example folder. 

Inside order ini, specifiy project directory, user account info etc.
Currently only "utm" and "gtiff" is suported in order_variables
list of availe product_list: ['source_metadata', 'l1', 'toa', 'bt', 'sr', 'toa', 'pixel_qa', 'aq_refl', 'et', 'stats',
                       'sr_ndvi', 'sr_evi', 'sr_savi', 'sr_msavi', 'sr_ndmi', 'sr_nbr', 'sr_nbr2']

Order_id field is not required for initial run, it will be polulated once order is created. 
Google cloud sotrage field is required for dowload script.

###Running Code###
All comands will be run from comand line directory as
(provisional_ssebop) D:\tott\Documents\Work_Projects\Provisional_ssebop_data\provisional_ssebop>

Navigate to <provisional_ssebop> directory and activate env

python bulk_order_data.py -ini example/order.ini

This will set up an order request to ESPA for images specified in id_list

Status can be checked on ESPA website.
Once orders (could be multiple if image list spanned multiple utm zones) are complete run the folowing to download:
python get_url_list.py -ini example/order.ini

This will dowlaod urls of each image ordered. 

Finally, to upload images to google bucket run:
python order_download.py -ini example/order.ini

This step will take some time

Each image uploaded to the cloud will be a composite image of specified products. 
The band names will be Band1, Band2, Band3 etc. 
The actual product name order will be at the end of the order_download.log file. 














