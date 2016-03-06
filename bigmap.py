#!/usr/bin/env python
# -*- coding: utf-8 -*-

__license__="New BSD"		# see https://en.wikipedia.org/wiki/BSD_licenses
__copyright__="Copyright 2010-2016, Pierre-Alain Dorange"
__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"
__version__="0.9"

"""
bigmap.py
----------------------------------------------------------------------------------------
Build a big image, by assembling small image from a Tile Map Server (TMS)
Works like OpenLayers.js of Leaflet.js

Download can be synchrnous or asynchronous (faster)
Tiles are assemble using PIL library, tiles are stored into a local cache to not overload TMS
	
bigmap main purpose is to help users creating big image from OSM map data to print (very) large maps
read carefully licences and notes before using, not all maps have same licence and usage policy
	
Some TMS require an API key (ie. MapBox), 
	please add your own API key into config.py to used those services
		
usage: python bigmap.py -h
supported TMS : python bigmap.py -d

See ReadMe.txt for detailed instructions
	
-- Requirements ------------------------------------------------------------------------
	Python 2.5
	PIL Library : <http://www.pythonware.com/products/pil/>
	ConfigObj : modified ConfigObj 4 <http://www.voidspace.org.uk/python/configobj.html>
	
-- Licences ----------------------------------------------------------------------------
	New-BSD Licence, (c) 2010-2016, Pierre-Alain Dorange
	See ReadMe.txt for instructions
	
-- Conventions -------------------------------------------------------------------------
	Geographical coordinates conform to (longitude,latitude) in degrees, 
		corresponding to (x,y) tiles coordinates
	TileMapService used Web Mercator projection (aka EPSG:3857 or WGS84/Pseudo-Mercator)
	
-- References --------------------------------------------------------------------------
	How web map works : https://www.mapbox.com/help/how-web-maps-work/
	TileMap Maths : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
	EPSG:3857 projection : https://en.wikipedia.org/wiki/Web_Mercator
	Quadkey for Bing : http://www.web-maps.com/gisblog/?m=200903
	Longitude : https://en.wikipedia.org/wiki/Longitude
	Latitude : https://en.wikipedia.org/wiki/Latitude
	
-- History -----------------------------------------------------------------------------
	0.1 initial alpha (september 2010)
	0.2 add openmapquest tiles (june 2011)
		+ troubles with MacOS 10.6 and threads (crash) : used LoadImage in main thread (1 thread only, not optimized)
	0.3 add stamen design maps : watercolor, terrain, toner (january 2013)
	0.4 enhance tiles server handling (march 2013)
		+ debug some platform specific issues
		+ add some CloudMade renders, Acetate and Google
	0.5 add box parameter, reorganize code
		add Nokia Maps + fix bing's quadkeys
	0.6 revert coordinates to follow general rules for coordinates and bbox
		add openmapsurfer renders
	0.7 add '*' wildcards for server name (can render several server at one time)
		add tile error handling for 404 errors
		add mapbox, apple, map1 and openport_weather servers
		cache better handling with maximum size
	0.8 reorganize tile servers (server.ini) : february 2015
		add api for mapbox (with API key) + new mapbox map
		add api for EarthData (Nasa Landsat live) with handle for specifing date (-d)
		removing cloudmade services (shutdown on april 2014)
		add -n option and location.ini to reach specific locations
	0.9 update mapbox API to new v4 TMS URL
		update all TMS and add some new one (lonvia, openrailway, wikimedia...)
		standardize coordinates : longitude (x) first then latitude (y) in all coordinates
		enable asynchronous download : can be from 1.4 to 4.6 faster depending on request
"""

# standard modules
import math
import os.path
import urllib2,socket
import threading,Queue
import sys
import getopt
import time
import re

urllib2.install_opener(urllib2.build_opener())		# just to disable a bug in MoxOS X 10.6 : force to load CoreFoundation in main thread

# required non-standard modules
from configobj import *				# read .INI file
from PIL import Image,ImageDraw		# Image manipulation library

# local
import config

# globals
_debug=False			# debug mode (verbose)
_compute=False			# display computed tiles coordinates (conversions from ongitude/latitude to pixels)

"""
	Utilities functions : compute some maths (tile coordinates to geographical latitude,longtitude...)
"""
	
def dtile2ll((dx,dy),zoom):
	""" 
		convert a tile differentiate coordinates (dx,dy) into a differentite (longitude, latitude), according to current zoom
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
	"""
	n=2.0**zoom
	lon_deg=359.0/n
	return (lon_deg,lon_deg)
	
def tilexy2quadkey((tx,ty),zoom):
	"""
		convert standard tile coordinates and zoom into a quadkey (used by Bing Tile servers)
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
	
def tilexy2ll((tx,ty),zoom):
	"""
		convert standard tile coordinates and zoom into a longitude,latitude
		code from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
	"""
	n=2.0**zoom
	lon_deg=360.0/n-180.0
	lat_rad=math.atan(math.sinh(math.pi*(1-2*ty/2)))
	lat_deg=math.degrees(lat_rad)
	return (lon_deg,lat_deg)
	
def convertFromTile(x,y,zoom):
	""" 
		convert a tile position(x,y) into a location (longitude, latitude) according to current zoom
		return a float coordinate
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
	"""
	n=2.0**zoom
	lon_deg=x/n*360.0-180.0
	lat_rad=math.atan(math.sinh(math.pi*(1-2*y/n)))
	lat_deg=math.degrees(lat_rad)
	
	return Coordinate(lon_deg,lat_deg)
    			
"""
	Class/objects
"""

class Coordinate():
	"""
		Coordinate : define a couple a value (longitude/latitude) to handle geographic coordinates
		handle algebric operation  : + - * /
		handle str conversion
		
		longitude : specify the east-west angular position (geographic coordinate) : -180° to +180°
		latitude  : specify the north-south angular position (geographic coordinate) : -90° to +90°
	"""
	def __init__(self,lon,lat):
		self.lon=lon
		self.lat=lat
		
	def __str__(self):
		return "(%.4f,%.4f)" % (self.lon,self.lat)
		
	def convert2Tile(self,zoom):
		""" 
			convert a location (longitude, latitude) into a tile position (x,y) according to current zoom
			return a float coordinate
			formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
		"""
		lat_rad=math.radians(self.lat)
		n=2.0**zoom
		x=(self.lon+180.0)/360.0*n
		y=(1.0-math.log(math.tan(lat_rad)+(1.0/math.cos(lat_rad)))/math.pi)/2.0*n
		return (x,y)
		
	def getResolution(self,server,zoom):
		"""
			Get resolution (meters per tile)
			formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
		"""
		lat_rad=math.radians(self.lat)
		r=(6378137.0*2.0*math.pi/server.tile_size)*math.cos(lat_rad)/(2.0**zoom)
		return r
		
	def __add__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.lat+other,self.lon+other)
		else:
			return Coordinate(self.lat+other.lat,self.lon+other.lon)
		
	def __sub__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.lat-other,self.lon-other)
		else:
			return Coordinate(self.lat-other.lat,self.lon-other.lon)
		
	def __mul__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.lat*other,self.lon*other)
		else:
			return Coordinate(self.lat*other.lat,self.lon*other.lon)
		
	def __div__(self,other):
		if (type(other)==int) or (type(other)==float):
			return Coordinate(self.lat/other,self.lon/other)
		else:
			return Coordinate(self.lat/other.lat,self.lon/other.lon)
		
class BoundingBox():
	""" 
		BoundingBox : handle a box define by geographical coordinates : up/left and bottom/right
		All coordinates are longitude/latitude
	"""
	def __init__(self,loc0,loc1):
		if loc0.lat>loc1.lat:
			lat0=loc1.lat
			lat1=loc0.lat
		else:
			lat0=loc0.lat
			lat1=loc1.lat
		if loc0.lon>loc1.lon:
			lon0=loc1.lon
			lon1=loc0.lon
		else:
			lon0=loc0.lon
			lon1=loc1.lon
		self.leftup=Coordinate(lon0,lat0)
		self.rightdown=Coordinate(lon1,lat1)
		
	def __str__(self):
		return "%s-%s" % (self.leftup,self.rightdown)
		
	def convert2Tile(self,zoom):
		(lon0,lat0)=self.leftup.convert2Tile(zoom)
		(lon1,lat1)=self.rightdown.convert2Tile(zoom)
		return ((lon0,lat1),(lon1,lat0))
		
class Cache():
	"""
		Cache : handle the local cache to avoid downloading manu times the same tile image
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
		self.use_cache=use_cache
		
	def buildpath(self,fname):
		return os.path.join(self.folder,fname)
		
	def incache(self,fpath):
		if self.use_cache:
			if os.path.isfile(fpath):
				dt=time.time()-os.path.getctime(fpath)
				if dt<=self.delay:	# reload tile if age exceeds cache delay
					return True
		return False
		
	def clear(self):
		# remove old files (delay)
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
		if sz>self.max_size:
			list=sorted(list,key=lambda tup:tup[1])
			i=0
			while sz>self.max_size:
				e=list[i]
				os.remove(e[0])
				sz-=e[2]
				i+=1				
		print "Cache size %.1f MB (max: %.1f MB)" % (1.0*sz/1048576.0, 1.0*self.max_size/1048576.0)
		
class TileServer():
	"""
		TileServer class : 
		define a tilemap server (TMS) and provide simple access to tiles
		TMS (or Slippy Map) use general convention, see : <http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames>
	"""
	def __init__(self,name,desc="",familly="",type="base"):
		self.name=name				# unique name to identity the map (provider.mapid ie. stamen.watercolor...)
		self.source=""				# the map source (url)
		self.description=desc		# a short description
		self.provider=""			# the map provider (ie. stamen)
		self.familly=familly		# map familly : general, 
		self.type=type				# map type : base, overlay
		self.base_url=""			# request url
		self.api_key=""				# apikey (some service required one)
		self.min_zoom=0				# min suported zoom
		self.max_zoom=0				# max supported zoom
		self.format="PNG"			# image format : default is PNG
		self.mode="RGB"				# pixel definition : default is RGB
		self.extension="png"		# file extension (according to image format)
		self.tile_size=config.default_tile_size	# tile pixels size
		self.size_x=config.default_tile_size	# tile pixels width
		self.size_y=config.default_tile_size	# tile pixels height
		self.tile_copyright=""		# tile copyright
		self.data_copyright=""		# data copyright
		self.handleDate=False		# can handle date (default is FALSE)
		self.server_list=None		
		self.current=0	
		
	def setServer(self,base_url,subdomain=None):
		self.base_url=base_url
		self.server_list=subdomain
		self.handleDate="{d}" in base_url
		
	def setZoom(self,min,max):
		self.min_zoom=min
		self.max_zoom=max
		
	def setTileSize(self,sx,sy):
		self.size_x=sx
		self.size_y=sy
		self.tile_size=sx
		
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
		
	def setCopyright(self,provider="",tile="",data=""):
		self.provider=provider
		self.tile_copyright=tile
		self.data_copyright=data
	
	def getZoom(self):
		return (min_zoom,max_zoom)
		
	def getCacheFName(self,(x,y),zoom,date=None):
		""" return the cache filename for a tile (x,y,z) """
		if self.handleDate and date:
			fname="%s_%d_%d_%d_%s.%s" % (self.name,zoom,x,y,date,self.extension)
		else:
			fname="%s_%d_%d_%d.%s" % (self.name,zoom,x,y,self.extension)
		return fname
	
	def getTileUrlFromXY(self,(tx,ty),zoom,date=None):
		"""
			return the tile url for this server according to tile coordinates, zoom value
			and specific format for this server using special tag :
				{x} 					: longitude (in tile geometry, integer)
				{y} 					: latitude (in tile geometry, integer)
				{z} {zoom} 				: zoom (integer)
				{q} 					: quadkey (microsoft encoding for x,y,z)
				{s:...} {switch:...}	: server subdomains (if any, ie. {s:a,b,c})
				{a} {api} 				: api key (if any)
				{d} {date} 				: date (YYYY-MM-DD)
		"""
		try:
			coord=0
			url=self.base_url
			if url.find("{x}")>=0:
				url=url.replace("{x}","%d" % tx)
				coord+=1
			if url.find("{y}")>=0:
				url=url.replace("{y}","%d" % ty)
				coord+=1
			if url.find("{z}")>=0 or url.find("{zoom}")>=0:
				url=url.replace("{z}","%d" % zoom)
				url=url.replace("{zoom}","%d" % zoom)
				coord+=1
			if url.find("{d}")>=0 and date:
				url=url.replace("{d}","%s" % date)
			if url.find("{q}")>=0:	# compute bing quadkey
				q=tilexy2quadkey((tx,ty),zoom)
				url=url.replace("{q}",q)
				coord+=3
			if url.find("{s}")>=0:
				if self.server_list:
					url=url.replace("{s}",self.server_list[self.current])
					self.current=self.current+1
					if self.current>=len(self.server_list):
						self.current=0
				else:
					raise
			if url.find("{apikey}")>=0 or  url.find("{a}")>=0:
				url=url.replace("{apikey}",self.api_key)
				url=url.replace("{a}",self.api_key)
			if coord<3:
				raise
		except:
			print "error, malformed server base url for %s\n%s\n%s" % (self.name,self.base_url,sys.exc_info())
		return url
		
	def show_licence(self):
		print "\tmap licence  : %s" % self.tile_copyright
		print "\tdata licence : %s" % self.data_copyright	

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
	
class LoadImagesFromURL(threading.Thread):
	"""	Thread for loading a tile from a tile server
		Can be used as an asynchronous thread (using start) or synchronous (using run)
		required :
			queue : data to be processed as tuple : (x,y,zoom,server,date,cache)
			result : return 0 if no error, 1 if error occured during loading
	"""
	def __init__(self,queue,result):
		threading.Thread.__init__(self)
		self.queue=queue
		self.result=result
		self.user_agent="%s/%s (urllib2/%s)" % (__file__,__version__,urllib2.__version__)
			
	def run(self):
		while not self.queue.empty():
			(x,y,zoom,server,date,cache)=self.queue.get()
			fname=server.getCacheFName((x,y),zoom,date)
			fpath=cache.buildpath(fname)
			if cache:
				load=not cache.incache(fpath)	# load if not in cache
			else:
				load=True
			if load:
				data=None
				tile_url=server.getTileUrlFromXY((x,y),zoom,date)
				headers={'User-Agent':self.user_agent}
				request=urllib2.Request(tile_url,None,headers)
				try:
					socket.setdefaulttimeout(config.k_server_timeout)
					stream=urllib2.urlopen(tile_url)
					header=stream.info()
					content=header.getheaders("Content-Type")
					if len(content)==0 or "text/" in content[0]:
						data=None
						if _debug:
							print "error for %s\n%s" % (tile_url,content)
					else:
						data=stream.read()
					stream.close()
				except urllib2.URLError,e:
					print "URLError:",e,"\n\t",tile_url
				except urllib2.HTTPError,e:
					print "HTTPError:",e,"\n\t",tile_url
				except socket.timeout,e:
					print "TimeOut:",e
				if data:	# get the data into an image file
					f=open(fpath,"wb")
					f.write(data)
					f.close()
					self.result.put(0)
				else:
					self.result.put(1)
			self.queue.task_done()

class BigMap():
	""" Assemble tile images into a big image 
	"""
	def __init__(self,server,zoom,date=None):
		self.bigImage=None
		self.server=server
		self.zoom=zoom
		self.filename=None
		(self.x0,self.y0)=(0,0)
		(self.x1,self.y1)=(0,0)
		self.markers=[]
		self.date=None
		
	def setSize(self,(x0,y0),(x1,y1)):
		(self.x0,self.y0)=(x0,y0)
		(self.x1,self.y1)=(x1,y1)
		(self.wx,self.wy)=(self.x1-self.x0+1,self.y1-self.y0+1)
			
	def setMarker(self,list):
		self.markers=list
		
	def build(self):
		""" create a large white image to fit the required size
			paste each individual tile image into it
			add markers if any
		"""
		self.bigImage=Image.new("RGBA",(self.server.tile_size*self.wx,self.server.tile_size*self.wy),"white")
		for x in range(self.x0,self.x1+1):
			for y in range(self.y0,self.y1+1) :
				fname=self.server.getCacheFName((x,y),self.zoom,self.date)
				fpath=os.path.join(config.k_cache_folder,fname)
				try:
					im=Image.open(fpath)
				except:		
					# no data, build an empty image (orange)
					im=Image.new("RGBA",(self.server.tile_size,self.server.tile_size),"orange")
				dest_pos=(self.server.tile_size*(x-self.x0),self.server.tile_size*(y-self.y0))
				self.bigImage.paste(im,dest_pos)
		if len(self.markers)>0:
			imd=ImageDraw.Draw(self.bigImage)
			for (mx,my,color,size) in self.markers:
				imd.ellipse([my-size,mx-size,my+size,mx+size],fill=color)
	
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
	
def LoadAPIKey(filename):
	"""
		Load API Key(s) and return a dictionnary for them
	"""
	dict={}
	try:
		keys=ConfigObj(filename)
		for k in keys:
			try:
				item=keys[k]
			except:
				print "Error: Can't find",s
				break
			try:
				api=item['api']
			except:
				print "Error: bad api",k
				break
			dict[k]=api
	except:
		dict={}
	return dict

def LoadLocation(filename):
	"""
		Load Location and return a dictionnary for them
		keys :
			box		box defining the area : 2 couples longitude/latitude
			zoom	zoom (option)
			name	name of the location (option)
			server	tile server (option)
	"""
	dict={}
	try:
		keys=ConfigObj(filename)
		for k in keys:
			try:
				item=keys[k]
			except:
				print "Error: Can't find",s
				break
			try:
				name=item['name']
			except:
				name=k
			try:
				l=item.as_floatList('box')
				a=Coordinate(l[0],l[1])
				b=Coordinate(l[2],l[3])
			except:
				print k,"requires a location"
				print sys.exc_info()
				break
			try:
				zoom=int(item['zoom'])
			except:
				zoom=16
			try:
				server=item['server']
			except:
				server=config.default_server
				
			dict[k]=(name,a,b,zoom,server)
	except:
		print "loading",filename,"error"
		print sys.exc_info()
		dict={}
	return dict
				
def LoadServers(filename):
	"""
		Load tiles server data from 'servers.ini' file, using keyword to get data :
			url (string) : the url syntax, see keys below for Base-URL
			zoom (integer list) : integer representing zoom min and max available for the map
		optionnal keys :
			subdomain (string list) : list of sub-domains for base-url
			size (interger list) : the x/y tile image size (default is 256,256)
			format (string) : the tile image format (default is PNG)
			mode (string) : the tile image mode (default is RGB)
			service (string) : the service provider
			desc (string) : a description of the map
			source (string) : the url source for the map
			familly (string) : a familly for the map
			type (string) : 'map' or 'overlay'
			data (string) : copyright string for the data of the map
			tile (string) : copyright string for the map design 
			api (string) : the API user key for protected services	

		base url, contain several keys, see : TileServer.getTileUrlFromXY() for details
	"""
	list=[]
	servers=ConfigObj(filename)
	for s in servers:
		try:
			item=servers[s]
		except:
			print "Error: Can't find",s
			break
		try:
			url=item['url']
		except:
			print "Error: bad url for",s
			break
		try:
			sub_domain=item['subdomain']
		except:
			sub_domain=None
		try:
			zoom=item.as_intList('zoom')
		except:
			print "Error: bad zoom (min,max) for",s
			break
		try:
			desc=item['desc']
		except:
			desc=""
		try:
			familly=item['familly']
		except:
			familly=""
		try:
			type=item['type']
		except:
			type="map"
		try:
			service=item['service']
		except:
			service=""
		try:
			data_copyright=item['data']
		except:
			data_copyright=""
		try:
			tile_copyright=item['tile']
		except:
			tile_copyright=""
		try:
			k=item['api']
			try:
				api_key=api_keys[k]
			except:
				print "Error: require an api key defined in api_key.ini for",s
				break			
		except:
			api_key=None
		try:
			format=item['format']
		except:
			format="PNG"
		try:
			mode=item['mode']
		except:
			mode="RGB"
		try:
			size=item.as_intList('size')
		except:
			size=(config.default_tile_size,config.default_tile_size)
		server=TileServer(s,desc,familly,type)
		server.setServer(url,sub_domain)
		server.setZoom(zoom[0],zoom[1])
		server.setCopyright(service,tile_copyright,data_copyright)
		server.setAPI(api_key)
		server.setFormat(format,mode)
		server.setTileSize(size[0],size[1])
		list.append(server)
		
	list.sort(key=lambda x : x.name)
	return list
	
def Usage():
	"""
		Display usage for the command (syntax and minimum help)
	"""
	print
	print "%s usage" % __file__
	print "\t-h (--help) : help"
	print "\t-d (--display) : show complete list of available servers"
	print "\t-o (--output) : specify output file name"
	print "\t-s (--server) : select servers from names (add '*' as first character to search a partial name)"
	print "\t-z (--zoom) : set zoom"
	print "\t-b (--box) : setbounding box (left,top,right,bottom)"
	print "\t-l (--location) : set location (longitude,latitude)"
	print "\t-t (--tile) : for centered download indicates width and height in meters"
	print "\t-m (--marker) : define a marker list file (text format)"
	print "\t-n (--name) : specify a location by its name (see locations.ini file)"
	print "\t-c (--cache) : override local tile cache"
	print "\t--date=date (YYYY-MM-DD) for EarthData realtime data"
	print "\t--test : test servers"
	print "Servers list : ",
	prefix=""
	for s in tile_servers:
		print prefix,s.name,
		prefix=","
	print
	
def ShowServers():
	""" Display a complete list of tile servers handled	"""
	print "%s tile servers list" % __file__
	for s in tile_servers:
		print s

def Do(server,box,zoom,cache,mlist=[],date=None,filename=None):
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
		print "** too many tiles : maximum request is %d tile(s)" % config.max_tiles
		print "\tyour request :",nt
		return
	if nt<=0:
		print "** ZERO tiles requested : (%d,%d) - (%d,%d)" % (x0,y0,x1,y1)
		return
	if zoom<server.min_zoom or zoom>server.max_zoom:
		print "%s : zoom %d is not available (zoom: %d-%d)" % (server.name,zoom,server.min_zoom,server.max_zoom)
		return
	print "%s : recovering %d tile(s)" % (server.name,nt)
				
	# create a task queue
	queue=Queue.Queue()
	result=Queue.Queue()
	for x in range(x0,x1+1):
		for y in range(y0,y1+1) :
			queue.put((x,y,zoom,server,date,cache))
		
	# handle the task queue
	if (config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queue
		for i in range(config.k_nb_thread):
			task=LoadImagesFromURL(queue,result)
			task.start()
		queue.join()
	else:	# for synchronous : run a single task until queue is empty
		task=LoadImagesFromURL(queue,result)
		task.run()

	# assemble tiles with PIL
	error=0
	while not(result.empty()):
		e=result.get()
		error+=e
		result.task_done()
	if error/nt<=config.max_errors:
		if error>0:
			print "%d errors, force map assembly" % error
		img=BigMap(server,zoom,date)
		img.setSize((x0,y0),(x1,y1))
		img.setMarker(mlist)
		img.build()
		fname=img.save(filename)
		#fname=BuildBigMap(server,zoom,(x0,y0),(x1,y1),mlist,date,filename)
		print "\tFile:",fname
	else:
		print "%d errors, too manay errors : no map generated" % t.error
		
	# always show credits and licences
	server.show_licence()
		
def main(argv):
	"""	Main : handle command line arguments and launch appropriate processes
	"""
	print '-------------------------------------------------'
		
	# 1/ extract and parse command line arguments to determine parameters
	try:
		opts,args=getopt.getopt(argv,"hdo:cb:l:s:z:n:m:",["help","display","output=","cache","box=","location=","server=","zoom=","tile=","date=","name=","marker="])
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
	date=time.strftime("%Y-%m-%d",time.localtime(time.time()))	# today/now
	server_names=(config.default_server,)
	use_cache=True
	test=False
	markerfile=None
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
				print "error location must be set as 2 float values",sys.exc_info()
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
				print "error location must be set as 4 float values",sys.exc_info()
				err+=1
		elif opt in ("-t","--tile"):
			try:
				list=arg.split(',')
				xwidth=float(list[1])
				ywidth=float(list[0])
				centered=True
			except:
				print "error width must be set as 2 int values",sys.exc_info()
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
				print "error location %s not defined" % arg
				print sys.exc_info()
				err+=1
		elif opt in ("-d","--display"):
			ShowServers()
			sys.exit()
		elif opt in ("-o","--output"):
			output_filename=arg
		elif opt=="--date":
			date=arg
		elif opt in ("-m","--marker"):
			markerfile=arg
		else:
			Usage()
			sys.exit()
			
	# read marker file (text) if any		
	mlist=[]
	if markerfile:
		f=open(markerfile,'r')
		for line in f:
			items=line.split('\t')
			mlist.append((float(items[0]),float(items[1]),items[2]))
		f.close()
	
	# define the match server(s) list
	match_servers=[]
	for n in server_names:
		for s in tile_servers:
			if re.search(n,s.name):
				match_servers.append(s)
			if s.name==n:
					match_servers.append(s)
	if len(match_servers)==0:
		print "no server known as",server_names
		Usage()	
		err+=1
	elif len(match_servers)>1:
		print "%d match servers :" % len(match_servers),
		prefix=""
		for s in match_servers:
			print "%s%s" % (prefix,s.name),
			prefix=", "
		print
					
	# 2/ do the job
	if err==0:	
		# 2.1/ Check/Create cache
		cache=Cache(config.k_cache_folder,config.k_cache_max_size,config.k_cache_delay)
		cache.setactive(use_cache)
		cache.clear()

		# 2.2/ lets go
		if config.k_chrono:
			t0 = time.time()		
		for s in match_servers:
			if (centered):
				r=location.getResolution(s,zoom)
				tx=(0.5*xwidth/r)/s.tile_size
				ty=(0.5*ywidth/r)/s.tile_size
				dx=360.0*tx/(2.0**zoom)
				dy=360.0*ty/(2.0**zoom)			
				downright=Coordinate(location.lon+dx,location.lat+dy)
				upleft=Coordinate(location.lon-dx,location.lat-dy)
				l=tilexy2ll((tx,ty),zoom)
				if _compute:	
					print "location       : %.5f, %.5f, zoom: %d" % (location.lon,location.lat,zoom)
					print "resolution     : %.5f m/pixel" % location.getResolution(s,zoom)
					print "Size (meters)  : %.2f, %.2f" % (xwidth,ywidth)
					print "Size (tiles)   : %.2f, %.2f" % (2*tx,2*ty)
					print "dl             : %.5f, %.5f, zoom: %d" % (l[0],l[1],zoom)
					print "Size (degrees) : %.5f, %.5f" % (2*dx,2*dy)
			else:
				location=(upleft+downright)/2
				if _compute:
					dy=(downright.lat-upleft.lat)/2
					dx=(downright.lon-upleft.lon)/2
					print "box    : (%.5f, %.5f) - (%.5f, %.5f)" % (upleft.lon,upleft.lat,downright.lon,downright.lat)
					print "center : %.5f, %.5f, zoom: %d" % (location.lon,location.lat,zoom)
					print "size   : %.5f, %.5f" % (2*dx,2*dy)
			mlist.append((location.lon,location.lat))
			box=BoundingBox(upleft,downright)
			if _compute:	
				(tile0,tile1)=box.convert2Tile(zoom)	
				print "Tile : ",tile0,tile1
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
					px=s.tile_size*(2.0**zoom)*dloc.lat/360.0
					py=-s.tile_size*(2.0**zoom)*dloc.lon/360.0
					marks.append((px,py,colors[index],12))
					index=index+1
					if index>=len(colors):
						index=0
					if _compute:
						print "Marker (loc)    : (%.5f,%.5f : %.5f" % (loc.lon,loc.lat,r)
						print "upleft (loc)    : (%.5f,%.5f)" % (upleft.lon,upleft.lat)
						print "upleft (tile)   : (%.2f,%.2f) > (%d,%d)" % (tile0[0],tile1[1],x0,y0)
						print "origin (loc)    : (%.5f,%.5f)" % (origin.lon,origin.lat)
						print "Marker (dloc)   : (%.5f,%.5f)" % (dloc.lon,dloc.lat)
						print "Marker (pixels) : (%.1f,%.1f)" % (px,py)
			if output_filename and len(match_servers)>1:
				filename="%s-%s" % (s.name,output_filename)
			else:
				filename=output_filename
			Do(s,box,zoom,cache,marks,date,filename)
		if config.k_chrono:
			t1 = time.time() - t0
			if config.k_chrono:
				print "processing : %.1f seconds" % (t1)
			t0 = time.time()
		
if __name__ == '__main__' :
	api_keys=LoadAPIKey("api_key.ini")
	tile_servers=LoadServers("servers.ini")
	locations=LoadLocation("locations.ini")
	main(sys.argv[1:])
