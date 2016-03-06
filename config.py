#!/usr/bin/env python
# -*- coding: utf-8 -*-

# default value (if no parameters), default location is Vieux Port, La Rochelle, France
default_loc0=(-1.15542,46.15839)		# (longitude,latitude)
default_loc1=(-1.14923,46.15525)
default_zoom=17
default_server="osm.default"

default_tile_size=256		# most TMS used 256 pixels wide tiles
max_tiles=300				# maximum tiles per request (to avoid bulk downloads)
max_errors=0.1				# maximum error rate to build the image

test_loc0=(-1.15367,46.15582)
test_loc1=test_loc0

# constants
k_nb_thread=2						# nb thread for asynchronous download. 0 or 1 is synchronous, 2 recommended
k_chrono=True						# measure duration on some action (debug)
k_cache_folder="cache"				# cache folder name
k_cache_delay=96.0*3600.0			# cache age : 96h (in seconds)
k_cache_max_size=100*1024*1024		# cache max size : 100 MB (in Bytes)
k_server_timeout=20					# server timeout in seconds
