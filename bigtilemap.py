#! /usr/bin/python3
# -*- coding: utf-8 -*-

__application__=__file__.split('/')[-1]		# get name of this python source file
__version__="1.0b5"
__license__="New BSD"		# see https://en.wikipedia.org/wiki/BSD_licenses
__copyright__="Copyright 2010-2024, Pierre-Alain Dorange"
__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"

# debug tags
_debug=False# debug mode (verbose)
_debug_thread=False
_debug_config=False
_compute=False			# display computed tiles coordinates (conversions from longitude/latitude to pixels)
_chrono=False

""" bigtilemap.py
----------------------------------------------------------------------------------------
Build a big image, by assembling small images from a Tile Map Server (TMS)
Works like "OpenLayers.js of Leaflet.js outside of a web browser"

Tiles (small image from TMS) are first download from TMS and store in a local cache
Then tiles are assembled into a big composite image (map).
Download can be synchrnous or asynchronous
	
bigtilemap main purpose is to help users creating big image from OSM map data to print (very) large maps
Read carefully licences and notes before using, maps have different licence and usage policy
	
Some TMS require an API key (ie. MapBox), 
	please add your own API key into api_key.ini to used those services
		
usage: python bigtilemap.py -h
supported TMS : python bigtilemap.py -d

bigtilemap.py is also used by pmx.py software (a map displayer with a tkinter GUI)

See ReadMe.txt for detailed instructions
	
-- Requirements ------------------------------------------------------------------------
	Python 3.9+
	PIL Library : <http://www.pythonware.com/products/pil/>
	
-- Licences ----------------------------------------------------------------------------
	New-BSD Licence, (c) 2010-2020, Pierre-Alain Dorange
	See ReadMe.txt for instructions
	
-- Conventions -------------------------------------------------------------------------
	Geographical coordinates conform to (longitude,latitude) in degrees, 
		corresponding to (x,y) tiles coordinates
	TileMapService used Web Mercator projection (aka EPSG:3857 or WGS84/Pseudo-Mercator)
	
-- References --------------------------------------------------------------------------
	WGS84 Geodesic system : https://en.wikipedia.org/wiki/World_Geodetic_System#WGS84
	Longitude : https://en.wikipedia.org/wiki/Longitude
	Latitude : https://en.wikipedia.org/wiki/Latitude
	How web map works : https://www.mapbox.com/help/how-web-maps-work/
	TileMap Maths : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
	EPSG:3857 projection : https://en.wikipedia.org/wiki/Web_Mercator
	Quadkey for Bing : http://www.web-maps.com/gisblog/?m=200903
	Nominatim (geographic search) : http://wiki.openstreetmap.org/wiki/Nominatim
	
-- History -----------------------------------------------------------------------------
	0.1 : september 2010
		initial
	0.2 : june 2011 :
		add openmapquest tiles
		troubles with MacOS 10.6 and threads (crash) : used LoadImage in main thread (1 thread only, not optimized)
	0.3 : january 2013
		add stamen design maps : watercolor, terrain, toner
	0.4 : march 2013
		enhance tiles server handling
		debug some platform specific issues
		add some CloudMade renders, Acetate and Google
	0.5 : december 2013
		add box parameter, reorganize code
		add Nokia Maps + fix bing's quadkeys
	0.6 : august 2014
		revert coordinates to follow general rules for coordinates and bbox
		add openmapsurfer renders
	0.7 : december 2014
		add '*' wildcards for server name (can render several server at one time)
		add tile error handling for 404 errors
		add mapbox, apple, map1 and openport_weather servers
		cache better handling with maximum size
	0.8 : february 2015 :
		reorganize tile servers (server.ini)
		add api for mapbox (with API key) + new mapbox map
		add api for EarthData (Nasa Landsat live) with handle for specifing date (-d)
		removing cloudmade services (shutdown on april 2014)
		add -n option and location.ini to reach specific locations
	0.9 : february 2016
		update mapbox API to new v4 TMS URL
		update all TMS and add some new one (lonvia, openrailway, wikimedia...)
		standardize coordinates : longitude (x) first then latitude (y) in all coordinates
		enable asynchronous download : can be from 1.4 to 4.6 faster depending on request
	1.0b1 : june 2016
		small updates for pmx.py
		update ESRI TMS services
		update EarthData (NASA) and better handle for GIBs date
		add a memory cache to optimize reloading (required for pmx)
		add a time shift for some earthdata (using day tag in servers.ini)
		add {w} tag for wikimapia special tag
		add error images for tiling
		add timeshift handling (for openweathermap)
	1.0b2 : august 2016
		add app_id in api description (for Here API)
	1.0b3 : august 2018
		add -f option for Nominatim with autoadjustement to size
		remove small bugs and fix some issues
	1.0b4 : june 2021
		prepare for python 3 compatibility
		removing configobj dependency (use configparser instead)
	1.0b5 : october 2022
		Go to python 3
		less dependency (no more ConfigObj go to standard configparser)
"""

# standard modules
import os.path, sys, getopt
import time
import math
import re
import socket
import threading
import codecs					# gestion des encodages de fichier

if sys.version_info.major==2:	# python 2.x
	import ConfigParser as configparser		# gestion fichier.INI (paramètres et configuration)
	import urllib2
	import Queue as queue
	urllib2.install_opener(urllib2.build_opener())		# just to disable a bug in MoxOS X 10.6 : force to load CoreFoundation in main thread
else:							# python 3.x
	import urllib.request,urllib.error,urllib.parse
	import queue
	import configparser						# gestion fichier.INI (paramètres et configuration)

# required non-standard modules
from PIL import Image,ImageDraw,PngImagePlugin		# Image manipulation library

# local
import config
import bigtilemap_nominatim

def tilexy2quadkey(tx,ty,zoom):
	""" convert standard tile coordinates and zoom into a quadkey (used by Bing Tile servers)
		code from : http://www.web-maps.com/gisblog/?m=200903	
	"""
	quadkey=""
	for i in range(zoom,0,-1):
		digit=0
		mask=1<<(i-1)
		if (tx&mask)!=0:
			digit+=1
		if (ty&mask)!=0:
			digit+=2
		quadkey+=str(digit)
	return quadkey

"""
	Class/objects
"""

class Coordinate():
	""" Coordinate : define a couple a value (longitude/latitude) to handle geographic coordinates
		according to WGS84 standard
		
		longitude : specify the east-west angular position (geographic coordinate) : -180° to +180°
		latitude  : specify the north-south angular position (geographic coordinate) : -90° to +90°
		coordinates are specified longitude first, latitude second.
		
		this class handle :
			* algebric operation  : + - * /
			* repr/str conversion
			* distance calculation
			* conversion to tile coordinate according to zoom
	"""
	def __init__(self,longitude=0.0,latitude=0.0):
		self.longitude=longitude
		self.latitude=latitude
		
	def __repr__(self):
		return "(%.4f,%.4f)" % (self.longitude,self.latitude)
		
	def __str__(self):
		if self.longitude<0.0:
			slon="%.4fW" % -self.longitude
		else:
			slon="%.4fE" % self.longitude
		if self.latitude<0.0:
			slat="%.4fN" % -self.latitude
		else:
			slat="%.4fS" % self.latitude
		return "(%s,%s)" % (slon,slat)
		
	def convert2Tile(self,zoom):
		""" convert a location (longitude, latitude) into a tile position (x,y) according to current zoom
			return a float coordinate
			formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
		"""
		lat_rad=math.radians(self.latitude)
		n=2.0**zoom
		x=(self.longitude+180.0)*n/360.0
		y=(1.0-math.log(math.tan(lat_rad)+(1.0/math.cos(lat_rad)))/math.pi)*n/2.0
		return (x,y)
	
	def convertFromTile(self,coord,zoom):
		""" convert standard (float) tile coordinates and zoom into a longitude,latitude
			code from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
		"""
		(x,y)=coord
		n=2.0**zoom
		self.longitude=x*360.0/n-180.0
		lat_rad=math.atan(math.sinh(math.pi*(1.0-2.0*y/n)))
		self.latitude=math.degrees(lat_rad)

	def getResolution(self,server,zoom):
		""" Get resolution (meters per tile)
			formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
		"""
		lat_rad=math.radians(self.latitude)
		r=(6378137.0*2.0*math.pi/server.size_x)*math.cos(lat_rad)/(2.0**zoom)
		return r
	
	def distance(self,B):
		""" Compute distance of the box diagonal, return value in kilometers
			using the simple earth as a sphere method : https://fr.wikipedia.org/wiki/Orthodromie
			assuming a nautic mile is 1/60 meridian arcand 1 nautic mile is 1852 meters
		"""
		lat_radA=math.radians(self.latitude)
		lat_radB=math.radians(B.latitude)
		lon_radA=math.radians(self.longitude)
		lon_radB=math.radians(B.longitude)
		a=math.sin(lon_radA)*math.sin(lon_radB)
		b=math.cos(lon_radA)*math.cos(lon_radB)*math.cos(lat_radB-lat_radA)
		d_rad=math.acos(a+b)
		d=1.852*60.0*math.degrees(d_rad)
		return d
		
	def __add__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.latitude+other,self.longitude+other)
		else:
			return Coordinate(self.latitude+other.latitude,self.longitude+other.longitude)
		
	def __sub__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.latitude-other,self.longitude-other)
		else:
			return Coordinate(self.latitude-other.latitude,self.longitude-other.longitude)
		
	def __mul__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.latitude*other,self.longitude*other)
		else:
			return Coordinate(self.latitude*other.latitude,self.longitude*other.longitude)
		
	def __div__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.latitude/other,self.longitude/other)
		else:
			return Coordinate(self.latitude/other.latitude,self.longitude/other.longitude)
		
	def __floordiv__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.latitude/other,self.longitude/other)
		else:
			return Coordinate(self.latitude/other.latitude,self.longitude/other.lon)
		
	def __truediv__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.latitude/other,self.longitude/other)
		else:
			return Coordinate(self.latitude/other.latitude,self.longitude/other.longitude)

class BoundingBox():
	""" BoundingBox : handle a box define by geographical coordinates : up/left and bottom/right
		All coordinates are longitude/latitude (see Coordinate object above)
		Composed of 2 Coordinate objects
	"""
	def __init__(self,loc0,loc1):
		if loc0.latitude>loc1.latitude:
			lat0=loc1.latitude
			lat1=loc0.latitude
		else:
			lat0=loc0.latitude
			lat1=loc1.latitude
		if loc0.longitude>loc1.longitude:
			lon0=loc1.longitude
			lon1=loc0.longitude
		else:
			lon0=loc0.longitude
			lon1=loc1.longitude
		self.leftup=Coordinate(lon0,lat0)
		self.rightdown=Coordinate(lon1,lat1)
	
	def __repr__(self):	
		return self.leftup+"-"+self.rightdown
		
	def __str__(self):
		return "%s-%s" % (self.leftup,self.rightdown)
		
	def convert2Tile(self,zoom):
		(lon0,lat0)=self.leftup.convert2Tile(zoom)
		(lon1,lat1)=self.rightdown.convert2Tile(zoom)
		return ((lon0,lat1),(lon1,lat0))
	
	def distance(self):
		""" Compute distance of the box diagonal """
		d=self.leftup.distance(self.rightdown)
		return d
		
	def size(self):
		""" Compute size (length and height) of the box """
		a2=Coordinate(self.leftup.longitude,self.rightdown.latitude)
		b2=Coordinate(self.rightdown.longitude,self.leftup.latitude)
		l=self.leftup.distance(a2)
		h=self.leftup.distance(b2)
		return(l,h)
		
class Cache():
	"""	Cache : handle the local cache to avoid downloading many times the same tile image
		cache has a maximum size (max_size in bytes) and images cached has a max delay (validity)
	"""
	def __init__(self,folder,max_size,delay):
		self.folder=folder
		self.use_cache=True
		self.max_size=max_size
		self.delay=delay

		# Just check is cache folder exist, create it if not
		if not os.path.exists(self.folder):
			os.makedirs(self.folder)	
			
	def setactive(self,use_cache=True):
		""" activate cache handling """
		self.use_cache=use_cache
		
	def buildpath(self,fname):
		""" return a valid path to cache image """
		return os.path.join(self.folder,fname)
		
	def incache(self,fpath):
		""" return True is image is allready in cache and is valid """
		if self.use_cache:
			if os.path.isfile(fpath):
				dt=time.time()-os.path.getctime(fpath)
				if dt<=self.delay:	# reload tile if age exceeds cache delay
					return True
		return False
		
	def getSize(self):
		""" return the current cache size """
		tsize=0
		for o in os.listdir(self.folder):
			f=os.path.join(self.folder,o)
			if os.path.isfile(f):
				tsize+=os.path.getsize(f)
		return tsize
		
	def clear(self):
		""" Clean the tile cache : remove old tiles 
				- tiles older than delay
				- tiles oldest when total cache size exceed limit
		"""
		# remove unvalid files (delay)
		for o in os.listdir(self.folder):
			f=os.path.join(self.folder,o)
			if os.path.isfile(f):
				s=os.path.getsize(f)
				dt=time.time()-os.path.getctime(f)
				if dt>self.delay:
					os.remove(f)
		# if total size too large, remove older ones
		sz=0
		list=[]
		for o in os.listdir(self.folder):
			f=os.path.join(self.folder,o)
			if os.path.isfile(f):
				d=os.path.getctime(f)
				s=os.path.getsize(f)
				sz+=s
				list.append((f,d,s))
		if sz>self.max_size:	# if total size greatest than limit, sort by date and remove oldest
			print("Cache too big, need cleaning :",ByteSize(sz))
			list=sorted(list,key=lambda tup:tup[1])
			i=0
			while sz>self.max_size:
				e=list[i]
				os.remove(e[0])
				sz-=e[2]
				i+=1
	
	def __repr__(self):
		return  "%s / %s" % (ByteSize(self.getSize()),ByteSize(self.max_size))
		
class ByteSize():
	""" Convert byte size (integer) into a human readable size
	"""
	def __init__(self,size):
		self.size=size
	
	def __repr__(self):
		units=('B','KB','MB','GB')
		s=self.size
		for i in units:
			if s<1024:
				return "%d %s" % (s,i)
			else:
				s=s>>10
		return "%d %s" % (s,units[2])
		
	def __str__(self):
		units=('B','KB','MB','GB')
		s=self.size
		for i in units:
			if s<1024:
				return "%d %s" % (s,i)
			else:
				s=s>>10
		return "%d %s" % (s,units[2])
		
class TileServer():
	""" TileServer class : 
		define a tilemap server (TMS) and provide simple access to tiles
		TMS (or Slippy Map) use general convention, see : <http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames>
	"""
	def __init__(self,name,desc="",familly="",type_str="base"):
		self.name=name				# unique name to identity the map (provider.mapid ie. stamen.watercolor...)
		self.source=""				# the map source (url)
		self.description=desc		# a short description
		self.provider=""			# the map provider (ie. stamen)
		self.familly=familly		# map familly : general, 
		self.type=type_str			# map type : base, overlay
		self.base_url=""			# request url
		self.api_key=""				# apikey (some service required one)
		self.min_zoom=0				# min suported zoom
		self.max_zoom=0				# max supported zoom
		self.format="PNG"			# image format : PNG / JPEG / GIF
		self.mode="RGB"				# pixel definition : RGB / RGBA (RGB with transparency)
		self.extension="png"		# file extension (according to image format)
#		self.tile_size=config.default_tile_size			# tile pixels size
		self.size_x=config.default_tile_size			# tile pixels width
		self.size_y=config.default_tile_size			# tile pixels height
		self.render_size_x=config.default_tile_size		# rendering tile pixels width
		self.render_size_y=config.default_tile_size		# rendering tile pixels height
		self.tile_copyright=""		# tile copyright
		self.data_copyright=""		# data copyright
		self.handleDate=False		# can handle date (default is FALSE)
		self.handleHour=False		# can handle date with hour (default is FALSE)
		self.handleTimeShift=False		# can handle timeshift (default is FALSE)
		self.dateDelay=0
		self.timeshift=0
		self.timeshift_value=[]
		self.timeshift_string=[]
		self.server_list=None		
		self.current=0	
		
	def setServer(self,base_url,subdomain=None,delay=0):
		self.base_url=base_url
		self.server_list=subdomain
		self.handleDate="{d}" in base_url
		self.handleHour="{dt}" in base_url
		self.handleTimeShift="{t}" in base_url
		self.dateDelay=delay
		
	def setZoom(self,min,max):
		self.min_zoom=min
		self.max_zoom=max
		
	def setTileSize(self,sx,sy,rx=config.default_tile_size,ry=config.default_tile_size):
		self.size_x=sx
		self.size_y=sy
		self.render_size_x=rx
		self.render_size_y=ry
#		self.tile_size=sx
		
	def setAPI(self,key=""):
		self.api_key=key
		
	def setFormat(self,fmt="PNG",mode="RGB"):
		self.format=fmt
		if fmt=="PNG":
			self.extension="png"
		elif fmt=="JPEG":
			self.extension="jpg"
		elif fmt=="GIF":
			self.extension="gif"
		
	def setTimeShift(self,ts_val,ts_str):
		self.timeshift_value=ts_val
		self.timeshift_string=ts_str
		
	def setCopyright(self,provider="",tile="",data=""):
		self.provider=provider
		self.tile_copyright=tile
		self.data_copyright=data
	
	def getZoom(self):
		return (self.min_zoom,self.max_zoom)
	
	def getBestZoom(self,box,coord):
		""" compute the best zoom to make visible the box area (BoundaryBox)
			in the physical area describe by (px, py) (pixels)
		"""
		(px,py)=coord
		if box==None:
			zoom=0
			if _compute: print("no box")
		else:
			distance=(box.rightdown-box.leftup)
			if distance.longitude==0.0 and distance.latitude==0.0:
				zoom=self.max_zoom
				if _compute: print("node box:",distance)
			else:
				zx=math.log((360.0*px)/(distance.longitude*self.size_x),2)
				zy=math.log((170.1022*py)/(distance.latitude*self.size_y),2)
				z=min(zx,zy)
				if z<self.min_zoom: zoom=self.min_zoom
				elif z>self.max_zoom: zoom=self.max_zoom
				else: zoom=int(z+0.5)
				if _compute:
					print("available physical size (pixels):",px,py)
					print("distance (degrees)",distance)
					print("zoom:",zx,zy,"max:",z)
					print("final zoom:",zoom)
		return zoom

	def getCacheFName(self,coord,zoom,date=None,timeshift=None):
		""" return the cache filename for a tile (x,y,z) 
		"""
		(x,y)=coord
		if self.handleDate:
			if date==None:
				date=time.strftime("%Y-%m-%d",time.localtime(time.time()-config.default_day_offset))
			fname="%s_%d_%d_%d_%s.%s" % (self.name,zoom,x,y,date,self.extension)
		elif self.handleTimeShift:
			if timeshift==None:
				timeshift=0
			fname="%s_%d_%d_%d_%s.%s" % (self.name,zoom,x,y,timeshift,self.extension)
		else:
			fname="%s_%d_%d_%d.%s" % (self.name,zoom,x,y,self.extension)
		return fname
	
	def getTileUrlFromXY(self,coord,zoom,date=None,timeshift=None):
		""" return the tile url for this server according to parameters :
				coord : tile coordinates : Coordinates object (x,y)
				zoom : zoom value : integer
				date (optionnal) : time.struct_time
				timeshift (optionnal), an index for multiple values : integer
			and specific format for this server using special url-tags :
				{x} {lon}				: longitude (in tile geometry, integer)
				{y} {lat}				: latitude (in tile geometry, integer)
				{z} {zoom} 				: zoom (integer)
				{s} {switch}			: server subdomains if any
				{q} 					: quadkey (microsoft encoding for x,y,z)
				{w}						: wikimapia NUM schema
				{g}						: google NUM schema
				{apikey} {api}			: api key (if any)
				{appid} 				: app identifier (if any)
				{d} {date} 				: date (YYYY-MM-DD)
				{dt} 	 				: date (YYYY-MM-DDTHH:MM)
				{t}						: time step, value in time_step tag, passed as date
			note: {x}, {y} and {z} (or {q}) are mandatory, other optional depending of server settings
		"""
		(tx,ty)=coord
		try:
			coords=0
			url=self.base_url
			if url.find("{x}")>=0 or url.find("{lon}")>=0:
				url=url.replace("{x}","%d" % tx)
				url=url.replace("{lon}","%d" % tx)
				coords+=1
			if url.find("{y}")>=0 or url.find("{lat}")>=0:
				url=url.replace("{y}","%d" % ty)
				url=url.replace("{lat}","%d" % ty)
				coords+=1
			if url.find("{z}")>=0 or url.find("{zoom}")>=0:
				url=url.replace("{z}","%d" % zoom)
				url=url.replace("{zoom}","%d" % zoom)
				coords+=1
			if url.find("{d}")>=0 or url.find("{date}")>=0:
				if date==None:		# no date, take current data-time
					date=localtime(time.time()-config.default_day_offset)
				t=time.mktime(date)
				if self.dateDelay!=0:
					if _debug: print("date/delay:",date,self.dateDelay)
					t=t+24.0*self.dateDelay*3600.0
				s=time.strftime("%Y-%m-%d",time.localtime(t))
				if _debug: print("final date:",s)
				url=url.replace("{date}","%s" % s)
				url=url.replace("{d}","%s" % s)
			if url.find("{dt}")>=0:
				if date==None:		# no date, take current data-time
					date=localtime(time.time()-config.default_day_offset)
				t=time.mktime(date)
				if self.dateDelay!=0:
					if _debug: print("date/delay:",date,self.dateDelay)
					t=t+24.0*self.dateDelay*3600.0
				s=time.strftime("%Y-%m-%dT%H:%M",time.localtime(t))
				url=url.replace("{dt}","%s" % s)
			if url.find("{t}")>=0:
				if timeshift==None:
					timeshift=0
				url=url.replace("{t}","%s" % self.timeshift_value[timeshift])
			if url.find("{q}")>=0:	# compute bing quadkey
				q=tilexy2quadkey(tx,ty,zoom)
				url=url.replace("{q}",q)
				coords+=3
			if url.find("{s}")>=0:
				if self.server_list:
					url=url.replace("{s}",self.server_list[self.current])
					self.current=self.current+1
					if self.current>=len(self.server_list):
						self.current=0
				else:
					raise
			if url.find("{w}")>=0:
				n=(tx%4)+4*(ty%4)
				url=url.replace('{w}','%d' % n)
			if url.find("{g}")>=0:
				n=(tx+ty)%4
				url=url.replace('{g}','%d' % n)
			if url.find("{apikey}")>=0 or url.find("{api}")>=0:
				url=url.replace("{apikey}",self.api_key[0])
				url=url.replace("{api}",self.api_key[0])
			if url.find("{appid}")>=0:
				url=url.replace("{appid}",self.api_key[1])
			if coords<3:	# test we got 3 coordinates params (x,y and z)
				raise
		except:
			print("error, malformed server base url for %s\n%s\n%s" % (self.name,self.base_url,sys.exc_info()))
		return url
		
	def show_licence(self):
		print("\tsource       : %s" % self.source)
		print("\tmap licence  : %s" % self.tile_copyright)
		print("\tdata licence : %s" % self.data_copyright)

	def __repr__(self):
		str="%s (zoom:%d-%d)" % (self.name,self.min_zoom,self.max_zoom)
		if len(self.familly)>0 :
			str=str+" [%s]" % self.familly
		if self.type=="overlay" :
			str=str+" [%s]" % self.type
		if len(self.provider)>0 :
			str=str+" by %s" % self.provider
		if len(self.description)>0 :
			str=str+"\n\t%s" % self.description
		str=str+"\n\tTile Licence: %s" % self.tile_copyright
		str=str+"\n\tData Licence: %s" % self.data_copyright
		return str

class ThreadData():
	""" data for asynchronous process (loading tiles) """
	def __init__(self,x,y,z,server,date=None,cache=None):
		self.locx=x
		self.locy=y
		self.zoom=z
		self.server=server
		self.date=date
		self.cache=cache
		
class LoadImagesFromURL(threading.Thread):
	""" Thread for loading a tile from a tile server
		Can be used as an asynchronous thread (using start) or synchronous (using run)
		required :
			queue : data to be processed as tuple : (x,y,zoom,server,date,timeshift,cache)
			result : return 0 if no error, 1 if error occured during loading
	"""
	def __init__(self,work,result,errorImage=None):
		threading.Thread.__init__(self)
		self.work=work
		self.result=result
		self.errorImage=errorImage
		self.user_agent="%s/%s" % (__application__,__version__)
			
	def run(self):
		while not self.work.empty():
			(x,y,zoom,server,date,timeshift,cache)=self.work.get()
			if _debug_thread:
				print("Thread, handle:",server.name,x,y,zoom)
			if x>0 and y>0 and zoom>0:
				# check if tile was in cache
				fname=server.getCacheFName((x,y),zoom,date,timeshift)
				if cache:
					fpath=cache.buildpath(fname)
					if cache:
						load=not cache.incache(fpath)
					else:
						load=True
				else:
					load=True
				if load:	# load if not in cache
					data=None
					tile_url=server.getTileUrlFromXY((x,y),zoom,date,timeshift)
					headers={'User-Agent':self.user_agent,'connection':'keep-alive'}
					request=urllib.request.Request(tile_url,None,headers)
					try:
						socket.setdefaulttimeout(config.k_server_timeout)
						stream=urllib.request.urlopen(request)
						header=stream.info()
						content=header.get("Content-Type")
						if len(content)==0 or "text/" in content[0]:
							data=None
							if _debug:
								print("error for %s\n%s" % (tile_url,content))
						else:
							data=stream.read()
						stream.close()
					except urllib.error.URLError as e:
						if self.errorImage:
							for err in config.urlError:
								if err in str(e):
									print("\t",err)
									data=self.errorImage[err]
							if not data:
								data=self.errorImage["default"]
						print("*URLError:",e,"\n\t",tile_url)
					except urllib.error.HTTPError as e:
						print("*HTTPError:",e,"\n\t",tile_url)
					except socket.timeout as e:
						print("*TimeOut:",e,"\n\t",tile_url)
					except:
						print("*Unknow error",sys.exc_info()[0],"\n\t",tile_url)
					else:
						if data and cache:	# save the data into an image file
							if data.__class__==PngImagePlugin.PngImageFile:
								data.save(fpath)
								self.result.put(1)
							else:
								f=open(fpath,"wb")
								f.write(data)
								f.close()
								self.result.put(0)
						else:
							self.result.put(1)
				else:
					self.result.put(0)
			self.work.task_done()

class BigTileMap():
	""" Assemble tile images into a big image 
	"""
	def __init__(self,server=None,zoom=0,date=None,timeshift=None,overlay=False):
		self.bigImage=None
		self.server=server
		self.zoom=zoom
		self.date=date
		self.timeshift=timeshift
		self.filename=None
		self.setSize((0,0),(0,0))
		self.markers=[]
		self.noData=None
		self.errorImage=None
		self.tile_cache=[]
		self.overlay=overlay
		self._debug_build=False
		
	def __repr__(self):
		s=""
		if self.server:
			s="Server: %s" % self.server
		else:
			s="Server: None"
		s=s+"\nZoom: %d" % self.zoom
		s=s+"\nTile cache: %d\n" % len(self.tile_cache)
		return s
	
	def setServer(self,server,zoom,date=None):
		self.server=server
		self.zoom=zoom
		self.date=date
		if self.overlay:
			self.noData=Image.new("RGBA",(self.server.size_x,self.server.size_y),(242,228,214,128))
		else:
			self.noData=Image.new("RGBA",(self.server.size_x,self.server.size_y),(242,228,214,255))
		
	def setSize(self,coord0,coord1):
		(self.x0,self.y0)=coord0
		(self.x1,self.y1)=coord1
		(self.wx,self.wy)=(self.x1-self.x0+1,self.y1-self.y0+1)
		if self.wx*self.wy!=0 and self.server:
			self.bigImage=Image.new("RGBA",(self.server.render_size_x*self.wx,self.server.render_size_y*self.wy))
	
	def getSize(self):
		return (self.wx*self.server.render_size_x,self.wy*self.server.render_size_y)
		
	def getImg(self):
		return self.bigImage
	
	def setMarker(self,list):
		self.markers=list
		
	def setErrorImage(self,imgDict):
		self.errorImage=imgDict
		
	def build(self,background=None):
		""" create a large white image to fit the required size
			paste each individual tile image into it
			add markers if any
			use a ram cache then a disk cache
		"""
		if _chrono: 
			t=time.clock()
			self.chrono=0.0
		if self.bigImage:
			for x in range(self.x0,self.x1+1):		# go through the matrix of tiles to build a bigger image (X,Y)
				for y in range(self.y0,self.y1+1):
					im=None
					if x>=0 and y>=0:
						fname=self.server.getCacheFName((x,y),self.zoom,self.date,self.timeshift)
						for (tname,timg) in self.tile_cache:
							if tname==fname:
								im=timg
								if self._debug_build:
									print(x,y,"tile in ram cache")
								break
						if not im:
							fpath=os.path.join(config.cachePath,fname)
							try:	# get tile from cache
								im=Image.open(fpath)
								self.tile_cache.append((fname,im))
								if len(self.tile_cache)>config.mem_cache:
									del self.tile_cache[0]
								if self._debug_build:
									print(x,y,"tile in disk cache")
							except:		
								# no data, build an empty image (orange)
								if not self.overlay: im=self.noData
								if self._debug_build:
									print(x,y,"no tile",sys.exc_info())
					if im:
#						dest_pos=(self.server.tile_size*(x-self.x0),self.server.tile_size*(y-self.y0))
						dest_pos=(self.server.render_size_x*(x-self.x0),self.server.render_size_y*(y-self.y0))
						if self.server.render_size_x!=self.server.size_x or self.server.render_size_y!=self.server.size_y:
							self.bigImage.paste(im.resize((self.server.render_size_x,self.server.render_size_y)),dest_pos)
						else:
							self.bigImage.paste(im,dest_pos)
			# add markers (if any)
			if len(self.markers)>0:
				imd=ImageDraw.Draw(self.bigImage)
				for (mx,my,color,size) in self.markers:
					imd.ellipse([my-size,mx-size,my+size,mx+size],fill=color)
		if _chrono: self.chrono=time.clock()-t
	
	def save(self,filename=None):
		if self.bigImage:
			# set filename (if not provided)
			if filename:
				self.filename=filename
			if self.filename:
				fname=self.filename
			else:
				if self.server.handleDate and self.date:
					fname="z%d_%dx%d_%s_%s.%s" % (self.zoom,self.wx,self.wy,self.server.name,self.date,self.server.extension)
				else:
					fname="z%d_%dx%d_%s.%s" % (self.zoom,self.wx,self.wy,self.server.name,self.server.extension)
			# set image data
			self.bigImage.info['source']=self.server.name
			self.bigImage.info['location']=''
			self.bigImage.info['data']=self.server.data_copyright
			self.bigImage.info['map']=self.server.tile_copyright
			self.bigImage.info['build']="%s/%s" % (__file__,__version__)
			# save
			self.bigImage.save(fname)
			return fname
		else:
			return None

class INILoader():
	""" Load INI file using configparser and some addons
	"""
	def __init(self,filename):
		self.filename=filename
		self.parser=None
		self.data={}
	
	def load(self):
		self.parser=configparser.ConfigParser()
		with codecs.open(self.filename,'r',encoding='utf-8') as f:
			self.parser.read_file(f)
		for section in self.parser.sections():
			item=self.parser[section]
			self.loadItem(item)
	
	def loadItem(self,item):
		return None
	
	def getList(self,value):
		if value==None:
			return None
		else:
			return list(filter(None, (x.strip() for x in value.split(","))))

	def getListInt(self,value):
		if value==None:
			return None
		else:
			return [int(v) for v in self.getList(value)]

	def getListFloat(self,value):
		if value==None:
			return None
		else:
			return [float(v) for v in self.getList(value)]

class ServerLoader(INILoader):
	def loadItem(self,item):
		return None

def getList(value):
	if value==None:
		return None
	else:
		return list(filter(None, (x.strip() for x in value.split(","))))

def getListInt(value):
	if value==None:
		return None
	else:
		return [int(x) for x in getList(value)]

def getListFloat(value):
	if value==None:
		return None
	else:
		return [float(x) for x in getList(value)]

def LoadAPIKey(filename):
	""" Load API Key(s) and return a dictionnary for them
	"""
	if _debug_config:
		print("loading API",filename)
	dict={}
	try:
		config=configparser.RawConfigParser()
		with codecs.open(filename,'r',encoding='utf-8') as f:
			if sys.version_info.major==2:
				config.readfp(f)
			else:
				config.read_file(f)
				
		for k in config.sections():
			if _debug_config:
				print("\tapikey",k)
			api=None
			app=None
			try:
				app=config.get(k,'app')
			except:
				pass
			try:
				api=config.get(k,'api')
			except:
				print("Error: bad api",k)
				break
			dict[k]=(api,app)
	except:
		print("ERROR loading",filename)
		print(sys.exc_info())
		dict={}
	if _debug_config:
		print("apis:",dict)
	return dict

def LoadLocation(filename):
	""" Load Location and return a dictionnary for them
		keys :
			box		box defining the area : 2 couples longitude/latitude
			zoom	zoom (option)
			name	name of the location (option)
			server	tile server (option)
	"""
	if _debug_config:
		print("loading Loc",filename)
	dict={}
	try:
		config=configparser.RawConfigParser()
		with codecs.open(filename,'r',encoding='utf-8') as f:
			if sys.version_info.major==2:
				config.readfp(f)
			else:
				config.read_file(f)
				
		for k in config.sections():
			try:
				name=config.get(k,'name')
			except:
				name=k
			try:
				l=config.get(k,'box').split(',')
				a=Coordinate(float(l[0]),float(l[1]))
				b=Coordinate(float(l[2]),float(l[3]))
			except:
				print(k,"requires a location (4 points, 4 values)")
				print(sys.exc_info())
				break
			try:
				zoom=int(config.get(k,'zoom'))
			except:
				zoom=16
			try:
				server=config.get(k,'server')
			except:
				server=config.default_server
				
			dict[k]=(name,a,b,zoom,server)
	except:
		print("loading",filename,"error")
		print(sys.exc_info())
		dict={}
	return dict

def LoadServers(filename,api_dict=None):
	""" Load tiles server data from 'servers.ini' file, using keyword to get data :
			url (string) : the url syntax, see keys below for Base-URL
			zoom (integer list) : integer representing zoom min and max available for the map
		optionnal keys :
			subdomain (string list) : list of sub-domains for base-url
			size (integer list) : the x/y tile image size (default is 256,256)
			render (integer list) : the x/y tile image size for rendering (default is 256,256)
			format (string) : the tile image format (default is PNG)
			mode (string) : the tile image mode (default is RGB)
			service (string) : the service provider
			desc (string) : a description of the map
			source (string) : the url source for the map
			familly (string) : a familly for the map
			type (string) : 'map' or 'overlay'
			data (string) : copyright string for the data of the map
			tile (string) : copyright string for the map design 
			api (string) : the API identifier key for protected services (apikey are in api_key.ini)
			day (integer) : time shit (in days)
			time_step (string list) : value for alternative subfolder in url (replace in {t})
			time_step_str (string list) : human readable value for time_step list
			cache (integer) : define a cache duration (hours)

		base url, contain several keys, see : TileServer.getTileUrlFromXY() for details
	"""
	if _debug_config:
		print("loading TMS",filename)
	servers_list=[]
	try:
		servers=configparser.RawConfigParser()
		with codecs.open(filename,'r',encoding='utf-8') as f:
			if sys.version_info.major==2:
				servers.readfp(f)
			else:
				servers.read_file(f)
				
		for section in servers.sections():
			# for each secton (server) get data from INI file
			item=servers[section]
			if _debug_config:
				print("\t",item)
			url=item.get('url',fallback=None)
			if url==None:
				print("Error: no or bad url for",section)
				break
			sub_domain=getList(item.get('subdomain',fallback=None))
			zoom=getListInt(item.get('zoom',fallback=[0.10]))
			desc=item.get('desc',fallback="")
			familly=item.get('familly',fallback="")
			tp=item.get('type',fallback="map")
			service=item.get('service',fallback="")
			delay=int(item.get('day',fallback="0"))
			ts_value=getList(item.get('time_step',fallback=""))
			ts_string=getList(item.get('time_step_str',fallback=""))
			data_copyright=item.get('data',fallback="")
			tile_copyright=item.get('tile',fallback="")
			k=item.get('api',fallback=None)
			api_key=None
			if k:
				try:
					api_key=api_dict[k]
				except:
					print("Error: require a valid api key defined in api_key.ini for",item)
					print("\t",k,"not found in",api_dict)
			fmt=item.get('format',fallback="PNG")
			mode=item.get('mode',fallback="RGB")
			size=getListInt(item.get('size',fallback="%d,%d" % (config.default_tile_size,config.default_tile_size)))
			render=getListInt(item.get('render',fallback="%d,%d" % (config.default_tile_size,config.default_tile_size)))
			# create the server and put data into
			server=TileServer(section,desc,familly,tp)
			server.setServer(url,sub_domain,delay)
			server.setZoom(zoom[0],zoom[1])
			server.setCopyright(service,tile_copyright,data_copyright)
			server.setAPI(api_key)
			server.setFormat(fmt,mode)
			server.setTileSize(size[0],size[1],render[0],render[1])
			server.setTimeShift(ts_value,ts_string)
			servers_list.append(server)
	except:
		print("loading",filename,"error")
		print(sys.exc_info())
		#servers_list=[]
	if _debug_config:
		print("***Server(s) loaded:\n",servers_list)
	servers_list.sort(key=lambda x : x.name)
	return servers_list
	
def Usage():
	""" Display usage for the command (syntax and minimum help)
	"""
	print()
	print("%s usage" % __file__)
	print("\t-h (--help) : help")
	print("\t-d (--display) : show complete list of available servers")
	print("\t-o (--output) : specify output file name")
	print("\t-s (--server) : select servers from names (add '*' as first character to search a partial name)")
	print("\t-z (--zoom) : set zoom")
	print("\t-b (--box) : setbounding box (left,top,right,bottom)")
	print("\t-l (--location) : set location (longitude,latitude)")
	print("\t-t (--tile) : for centered download indicates width and height in meters")
	print("\t-f (--find) : for Nominatim search")
	print("\t-m (--marker) : define a marker list file (text format)")
	print("\t-n (--name) : specify a location by its name (see locations.ini file)")
	print("\t-c (--cache) : override local tile cache")
	print("\t--date=date (YYYY-MM-DD) for EarthData realtime data")
	print("\t--test : test servers")
	print("Servers list : ",)
	prefix=""
	for s in tile_servers:
		print(prefix,s.name,)
		prefix=","
	print
	
def ShowServers():
	""" Display a complete list of tile servers handled	"""
	print("%s tile servers list" % __file__)
	for s in tile_servers:
		print(s)

def Do(server,box,zoom,cache,mlist=[],date=None,timeshift=None,filename=None):
	""" Execute the request :
		load map tiles asynchronously from a map servers inside the box at zoom, 
		using or not the cache. then assemble tiles into a big image
	"""
	# compute coordinates and tiles number
	(tile0,tile1)=box.convert2Tile(zoom)
	(x0,y0)=(int(tile0[0]),int(tile0[1]))
	(x1,y1)=(int(tile1[0]),int(tile1[1]))
	nt=(x1-x0+1)*(y1-y0+1)
	if nt>config.max_tiles:
		print("** too many tiles : maximum request is %d tile(s)" % config.max_tiles)
		print("\tyour request :",nt)
		return
	if nt<=0:
		print("** ZERO tiles requested : (%d,%d) - (%d,%d)" % (x0,y0,x1,y1))
		return
	if zoom<server.min_zoom or zoom>server.max_zoom:
		print("** %s : zoom %d is not available (zoom: %d-%d)" % (server.name,zoom,server.min_zoom,server.max_zoom))
		return
	print("processing %s : recovering %d tile(s)" % (server.name,nt))
				
	# create a task queue
	inputQueue=queue.Queue()
	resultQueue=queue.Queue()
	for x in range(x0,x1+1):
		for y in range(y0,y1+1) :
			inputQueue.put((x,y,zoom,server,date,timeshift,cache))
		
	# handle the task queue
	if (config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queue
		for i in range(config.k_nb_thread):
			task=LoadImagesFromURL(inputQueue,resultQueue)
			task.start()
		inputQueue.join()
	else:	# for synchronous : run a single task until queue is empty
		task=LoadImagesFromURL(inputQueue,resultQueue)
		task.run()

	# assemble tiles with PIL
	error=0
	while not(resultQueue.empty()):
		e=resultQueue.get()
		error+=e
		resultQueue.task_done()
	if error/nt<=config.max_errors:
		if error>0:
			print("%d errors, force map assembly" % error)
		img=BigTileMap(server,zoom,date)
		img.setSize((x0,y0),(x1,y1))
		img.setMarker(mlist)
		img.build()
		fname=img.save(filename)
		#fname=BuildBigTileMap(server,zoom,(x0,y0),(x1,y1),mlist,date,filename)
		print("\tFile:",fname)
	else:
		print("%d errors, too many errors : no map generated" % error)
		
	# always show credits and licences
	server.show_licence()

def do_test(servers_list):
	(x,y)=(16357,11699)
	zoom=15
	date=None
	timeshift=None
	cache=None
	total_errors=0
	for s in servers_list:
		print("--",s.name,"-----")
		(mini,maxi)=s.getZoom()
		zoom=maxi
		# create a task queue
		t0=time.time()
		inputQueue=queue.Queue()
		outputQueue=queue.Queue()
		queue.put((x,y,zoom,s,date,timeshift,cache))
		task=LoadImagesFromURL(inputQueue,outputQueue)
		task.run()
		while not(outputQueue.empty()):
			e=outputQueue.get()
			outputQueue.task_done()
		t0=time.time()-t0
		print("\t%.1f secondes" % t0)
	print("--------")
		
def main(argv):
	"""	Main : handle command line arguments and launch appropriate processes
	"""
	print('-------------------------------------------------')
		
	# 1/ extract and parse command line arguments to determine parameters
	try:
		opts,args=getopt.getopt(argv,"hdo:cb:l:s:z:n:f:m:",["help","display","output=","cache","box=","location=","server=","zoom=","tile=","date=","name=","find=","marker=","test"])
	except:
		Usage()
		sys.exit(2)
		
	# default value (if no arguments)
	output_filename=None
	centered=False
	upleft=Coordinate(config.default_loc0[0],config.default_loc0[1])
	downright=Coordinate(config.default_loc1[0],config.default_loc1[1])
	location=(upleft+downright)/2
	zoom=config.default_zoom
	(xwidth,ywidth)=(100.0,100.0)
	date=time.strftime("%Y-%m-%d",time.localtime(time.time()-config.default_day_offset))	# the prevous day
	timeshift=None
	server_names=(config.default_server,)
	use_cache=True
	testmode=0
	markerfile=None
	nominatim=None
	err=0
	
	# handle arguments
	for opt,arg in opts:
		if opt in ("-c","--cache"):
			use_cache=False
		elif opt in ("-l","--location"):
			try:
				list=arg.split(',')
				location=Coordinate(float(list[0]),float(list[1]))
				centered=True
			except:
				print("error location must be set as 2 float values",sys.exc_info())
				err+=1
		elif opt in ("-s","--server"):
			server_names=arg.split(',')
		elif opt in ("-z","--zoom"):
			zoom=int(arg)
		elif opt in ("-b","--box"):
			try:
				list=arg.split(',')
				upleft=Coordinate(float(list[0]),float(list[1]))
				downright=Coordinate(float(list[2]),float(list[3]))
				centered=False
			except:
				print("error location must be set as 4 float values",sys.exc_info())
				err+=1
		elif opt in ("-t","--tile"):
			try:
				list=arg.split(',')
				xwidth=float(list[1])
				ywidth=float(list[0])
				centered=True
			except:
				print("error width must be set as 2 int values",sys.exc_info())
				err+=1
		elif opt in ("-n","--name"):
			try:
				output_filename="%s.png" % locations[arg][0]
				upleft=locations[arg][1]
				downright=locations[arg][2]
				zoom=locations[arg][3]
				server_names=(locations[arg][4],)
				centered=False
			except:
				print("error location %s not defined" % arg)
				print(sys.exc_info())
				err+=1
		elif opt in ("-f","--find"):
			try:
				url=bigtilemap_nominatim.query_url((arg,))
				if url.download()==0:
					results=url.xml_parse()
					if len(results)>0:
						r=results[0]
						print("RESULT: %s/%s\n\t%s"% (r.familly,r.type,r.fullname))
						if r.box:
							upleft=r.box.leftup
							downright=r.box.rightdown
							centered=False
						else:
							location=r.location
							centered=True
					else:
						print("No result using Nominatim for:",arg)
			except:
				print("error with query %s" % arg)
				print(sys.exc_info())
				err+=1
		elif opt in ("-d","--display"):
			ShowServers()
			sys.exit()
		elif opt in ("-o","--output"):
			output_filename=arg
		elif opt=="--date":
			date=time.strptime("%Y-%m-%d",arg)
		elif opt in ("-m","--marker"):
			markerfile=arg
		elif opt in ("--test",):
			print("test option activated")
			testmode=1
		else:
			Usage()
			sys.exit()
	
	if testmode>0:
		do_test(tile_servers)
	else:
		# read marker file (text) if any
		mlist=[]
		if markerfile:
			f=open(markerfile,'r')
			for line in f:
				items=line.split('\t')
				mlist.append((float(items[0]),float(items[1]),items[2]))
			f.close()
		
		# define the match server(s) list : using a list of name (server_names) comparing with server.name
		match_servers=[]
		for n in server_names:
			for s in tile_servers:
				if s.name==n:
					match_servers.append(s)
				elif re.search(n,s.name):
					match_servers.append(s)
		if len(match_servers)==0:
			print("no server matching for:",server_names)
			Usage()	
			err+=1
		elif len(match_servers)>1:
			print("%d matching servers :" % len(match_servers),)
			prefix=""
			for s in match_servers:
				print("%s%s" % (prefix,s.name),)
				prefix=", "
			print()
						
		# 2/ do the job
		if err==0:	
			# 2.1/ Check/Create cache
			cache=Cache(config.cachePath,config.k_cache_max_size,config.k_cache_delay)
			cache.setactive(use_cache)
			cache.clear()
			print(cache)

			# 2.2/ lets go
			if config.k_chrono:
				t0 = time.time()		
			for s in match_servers:
				if (centered):
					r=location.getResolution(s,zoom)
					tx=(0.5*xwidth/r)/s.size_x
					ty=(0.5*ywidth/r)/s.size_y
					dx=360.0*tx/(2.0**zoom)
					dy=360.0*ty/(2.0**zoom)			
					downright=Coordinate(location.lon+dx,location.lat+dy)
					upleft=Coordinate(location.lon-dx,location.lat-dy)
					l=tilexy2ll((tx,ty),zoom)
					if _compute:	
						print("location       : %.5f, %.5f, zoom: %d" % (location.lon,location.lat,zoom))
						print("resolution     : %.5f m/pixel" % location.getResolution(s,zoom))
						print("Size (meters)  : %.2f, %.2f" % (xwidth,ywidth))
						print("Size (tiles)   : %.2f, %.2f" % (2*tx,2*ty))
						print("dl             : %.5f, %.5f, zoom: %d" % (l[0],l[1],zoom))
						print("Size (degrees) : %.5f, %.5f" % (2*dx,2*dy))
				else:
					location=(upleft+downright)/2
					if _compute:
						dy=(downright.lat-upleft.lat)/2
						dx=(downright.lon-upleft.lon)/2
						print("box    : (%.5f, %.5f) - (%.5f, %.5f)" % (upleft.lon,upleft.lat,downright.lon,downright.lat))
						print("center : %.5f, %.5f, zoom: %d" % (location.lon,location.lat,zoom))
						print("size   : %.5f, %.5f" % (2*dx,2*dy))
				box=BoundingBox(upleft,downright)
				print("Box size (km): %.2f, %.2f" % box.size())
				if _compute:	
					(tile0,tile1)=box.convert2Tile(zoom)	
					print("Tile : ",tile0,tile1)
				marks=[]
				if len(mlist)>0:	# handle markers
					colors=["red","blue","green","orange","black","cyan","magenta","yellow","white"]
					index=0
					r=location.getResolution(s,zoom)
					(tile0,tile1)=box.convert2Tile(zoom)
					(x0,y0)=(int(tile0[0]),int(tile0[1]))
					origin=convertFromTile(x0,y0,zoom)
					for marker in mlist:
						loc=Coordinate(marker[0],marker[1])
						dloc=loc-origin
						px=s.size_x*(2.0**zoom)*dloc.lat/360.0
						py=-s.size_y*(2.0**zoom)*dloc.lon/360.0
						marks.append((px,py,colors[index],12))
						index=index+1
						if index>=len(colors):
							index=0
						if _compute:
							print("Marker (loc)    : (%.5f,%.5f : %.5f" % (loc.lon,loc.lat,r))
							print("upleft (loc)    : (%.5f,%.5f)" % (upleft.lon,upleft.lat))
							print("upleft (tile)   : (%.2f,%.2f) > (%d,%d)" % (tile0[0],tile1[1],x0,y0))
							print("origin (loc)    : (%.5f,%.5f)" % (origin.lon,origin.lat))
							print("Marker (dloc)   : (%.5f,%.5f)" % (dloc.lon,dloc.lat))
							print("Marker (pixels) : (%.1f,%.1f)" % (px,py))
				if output_filename and len(match_servers)>1:
					filename="%s-%s" % (s.name,output_filename)
				else:
					filename=output_filename
				Do(s,box,zoom,cache,marks,date,timeshift,filename)
			if config.k_chrono:
				t1 = time.time() - t0
				if config.k_chrono:
					print("processing : %.1f seconds" % (t1))
				t0 = time.time()

# main (load essential config file (as global data) then run
api_keys=LoadAPIKey(config.api_keys_path)
tile_servers=LoadServers(config.tile_servers_path,api_keys)
locations=LoadLocation(config.locations_path)

if __name__ == '__main__' :
	main(sys.argv[1:])
