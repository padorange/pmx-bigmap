#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# default value (if no parameters), 

# default location is "Vieux Port, La Rochelle, France"
#	rendered with openstreetmap default map at zoom 17
default_query='Tour St-Nicolas, La Rochelle, France'
default_loc0=(-1.15542,46.15839)		# (longitude,latitude)
default_loc1=(-1.14923,46.15525)
default_zoom=17
default_server="osm.default"
default_day_offset=86400

default_tile_size=256				# most TMS used 256 pixels wide tiles
max_tiles=300						# maximum tiles per request (to avoid bulk downloads)
max_errors=0.1						# maximum error rate to build the image
mem_cache=50						# memory cache size (tiles) for faster rendering (pmx)

test_loc0=(-1.15367,46.15582)
test_loc1=test_loc0

# constants
k_nb_thread=2						# nb thread for asynchronous download. 
									# 	0 or 1 is synchronous, 2 threads recommended
k_chrono=True						# measure duration on some action (debug)
k_cache_delay=96.0*3600.0			# cache age : 96h (in seconds)
k_cache_max_size=100*1024*1024		# cache max size : 100 MB (in Bytes)
k_server_timeout=20					# server timeout in seconds

# config files
_resourcesPath="resources"			# local path for ressources (error images, some icons...)
_workingdir="bigtilemap"			# working directory (in user home) for storing data
_cachedir="cache"					# cache directory (in _workingdir)
api_keys_file="api_key.ini"			# api key list (config file)
tile_servers_file="servers.ini"		# TMS server liste (config file)
locations_file="locations.ini"		# location list (config file)
pmx_db_file="pmx.db"				# parameter database (sqlite) stored in _workingdir

# == handle local directory =======================================
# create the data directory and set paths for internal data and user data
# the default directory is the source code directory, user data are stored in user folder (subfolder "ndsreader")

import sys,os.path

# define source directory (where the OS is currently, at the run time)
prgdir=os.path.dirname(os.path.abspath(sys.argv[0]))

# set working directory to user home directory (to store user data)
wrkdir=os.path.join(os.path.expanduser("~"),_workingdir)
if not os.path.exists(wrkdir):		# create dir if it does not exist
	os.makedirs(wrkdir)

# set OS default directory to source directory (for internal in/out files, make launch independant location for files))
os.chdir(prgdir)

print("default dir", prgdir)
print("data dir", wrkdir)

# == Create file paths =======================================
dbPath=os.path.join(wrkdir,pmx_db_file)
cachePath=os.path.join(wrkdir,_cachedir)
api_keys_path=os.path.join(prgdir,api_keys_file)
tile_servers_path=os.path.join(prgdir,tile_servers_file)
locations_path=os.path.join(prgdir,locations_file)
loadingImgPath=os.path.join(prgdir,_resourcesPath,"loading.png")	# file path for the loading logo)
urlError=('default','400','401','403','404','timeout')				# file paths for error tiles
errorImgPath={}
for e in urlError:
	errorImgPath[e]=os.path.join(prgdir,_resourcesPath,"%s.png" % e)
