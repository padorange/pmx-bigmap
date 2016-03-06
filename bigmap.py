#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	bigmap.py
	-------------
	Download tiles from a Tile Server (asynchronous) and assemble tiles into a big Map
	Assemble tiles with PIL library
	
	bigmap main purpose is to help users creating big image from OSM map data to print (very) large maps
	read carefully licences and notes before using, not all maps have same licence and usage policy
		
	usage: python bigmap.py -h
	supported servers : python bigmap.py -d

	See ReadMe.txt for detailed instructions
	
	Requirements
	------------
	Python 2.7
	PIL Library : <http://www.pythonware.com/products/pil/>
	ConfigObj : modified ConfigObj 4 <http://www.voidspace.org.uk/python/configobj.html>
	
	Licences
	--------
	New-BSD Licence, (c) 2010-2013, Pierre-Alain Dorange
	See ReadMe.txt for instructions
	
	History
	-------
	0.1 initial release (september 2010)
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
		
"""

__version__="0.7"
__contact__="pdorange@mac.com"

# standard modules
import math
import os.path
import urllib2,socket
import threading
import sys
import getopt
import time
import re

# required modules
from configobj import *		# read .INI file
from PIL import Image		# Image manipulation library

# local
import config

# globals
kHTTP_User_Agent="bigmap_bot %s (%s)" % (__version__,__contact__)
kHTTP_Time_Out=5
debug=True
max_tiles=300

"""
	Utilities functions : compute some maths (tile coordinates to geographical latitude,longtitude...)
"""

def ll2tile((latitude,longitude),zoom):
	""" 
		convert a location (longitude, latitude) into a tile position (x,y), according to current zoom
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
	"""
	lat_rad=math.radians(latitude)
	n=2.0**zoom
	xtile=int((longitude+180.0)/360.0*n+0.5)
	ytile=int((1.0-math.log(math.tan(lat_rad)+(1/math.cos(lat_rad)))/math.pi)/2.0*n+0.5)
	
	return (xtile,ytile)

def ll2xy((latitude,longitude),zoom):
	""" 
		convert a location (longitude, latitude) into a tile position (x,y), according to current zoom
		same as ll2tile, but return a float coordinate
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
	"""
	lat_rad=math.radians(latitude)
	n=2.0**zoom
	x=(longitude+180.0)/360.0*n
	y=(1.0-math.log(math.tan(lat_rad)+(1.0/math.cos(lat_rad)))/math.pi)/2.0*n
	return (x,y)
	
def tile2ll((x,y),zoom):
	""" 
		convert a tile coordinates (x,y) into a location (longitude, latitude), according to current zoom
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
	"""
	n=2.0**zoom
	lon_deg=x/n*360.0-180.0
	lat_rad=math.atan(math.sinh(math.pi*(1-2*y/n)))
	lat_deg=math.degrees(lat_rad)
	return (lon_deg,lat_deg)
	
def dtile2ll((dx,dy),zoom):
	""" 
		convert a tile coordinates (x,y) into a location (longitude, latitude), according to current zoom
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
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
    			
"""
	Class/objects
"""
class Coordinate():
	def __init__(self,x,y):
		self.x=x
		self.y=y
		
	def __str__(self):
		return "(%.4f,%.4f)" % (self.x,self.y)
		
	def convert2Tile(self,server,zoom):
		""" 
			convert a location (longitude, latitude) into a tile position (x,y), according to current zoom
			same as ll2tile, but return a float coordinate
			formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
		"""
		lat_rad=math.radians(self.x)
		n=2.0**zoom
		x=(self.y+180.0)/360.0*n
		y=(1.0-math.log(math.tan(lat_rad)+(1.0/math.cos(lat_rad)))/math.pi)/2.0*n
		return (x,y)
		
class BoundingBox():
	def __init__(self,loc0,loc1):
		if loc0.x>loc1.x:
			x0=loc1.x
			x1=loc0.x
		else:
			x0=loc0.x
			x1=loc1.x
		if loc0.y>loc1.y:
			y0=loc1.y
			y1=loc0.y
		else:
			y0=loc0.y
			y1=loc1.y
		self.upleft=Coordinate(x0,y0)
		self.downright=Coordinate(x1,y1)
		
	def __str__(self):
		return "%s-%s" % (self.upleft,self.downright)
		
	def convert2Tile(self,server,zoom):
		(x0,y0)=self.upleft.convert2Tile(server,zoom)
		(x1,y1)=self.downright.convert2Tile(server,zoom)
		return ((x0,y1),(x1,y0))
		
class Cache():
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
		# remove old files
		for o in os.listdir(self.folder):
			f=os.path.join(self.folder,o)
			if os.path.isfile(f):
				s=os.path.getsize(f)
				dt=time.time()-os.path.getctime(f)
				if dt>self.delay:
					os.remove(f)
		# if total size too large, remove older
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
		print "cache size %.1f MB" % (1.0*sz/1048576.0)
		
class TileServer():
	"""
		TileServer class : 
		define de tile server and provide simple access to tiles
		Tile Servers (or Slippy Map) use general convention, see : <http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames>
	"""
	def __init__(self,name):
		self.name=name
		self.source=""
		self.description=""
		self.familly=""
		self.type=""
		self.base_url=""
		self.server_list=None
		self.api_key=""
		self.tile_size=config.default_tile_size
		self.min_zoom=0
		self.max_zoom=0
		self.format="PNG"
		self.mode="RGB"
		self.extension="png"
		self.size_x=config.default_tile_size
		self.size_y=config.default_tile_size
		self.tile_copyright=""
		self.data_copyright=""
		
	def setServer(self,base_url,subdomain=None):
		self.base_url=base_url
		self.server_list=subdomain
		self.current=0
		
	def setZoom(self,min,max):
		self.min_zoom=min
		self.max_zoom=max
		
	def setTileSize(self,sx,sy):
		self.size_x=sx
		self.size_y=sy
		
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
		
	def setCopyright(self,tile="",data=""):
		self.tile_copyright=tile
		self.data_copyright=data
	
	def getZoom(self):
		return (min_zoom,max_zoom)
	
	def getTileUrlFromXY(self,(tx,ty),zoom):
		"""
			return the tile url for this server according to tile coordinates and zoom value
		"""
		try:
			coord=0
			url=self.base_url
			if url.find("[x]")>=0:
				url=url.replace("[x]","%d" % tx)
				coord+=1
			if url.find("[y]")>=0:
				url=url.replace("[y]","%d" % ty)
				coord+=1
			if url.find("[z]")>=0:
				url=url.replace("[z]","%d" % zoom)
				coord+=1
			if url.find("[q]")>=0:	# compute bing quadkey
				q=tilexy2quadkey((tx,ty),zoom)
				url=url.replace("[q]",q)
				coord+=3
			if url.find("[s]")>=0:
				if self.server_list:
					url=url.replace("[s]",self.server_list[self.current])
					self.current=self.current+1
					if self.current>=len(self.server_list):
						self.current=0
				else:
					raise
			if url.find("[a]")>=0:
				url=url.replace("[a]",self.api_key)
			if coord<3:
				raise
		except:
				print "error, malformed server base url",self.base_url,sys.exc_info()
		return url

class LoadImageFromURL(threading.Thread):
	"""
		Thread for loading tile from a tile server
		Can be used as an asynchronous thread (using start) or synchronous (using run)
	"""
	def __init__(self,server,zoom,tileList):
		threading.Thread.__init__(self)
		self.server=server
		self.zoom=zoom
		self.tileList=tileList
		self.done=[]
		self.n=0
		self.error=0
			
	def run(self,cache):
		self.n=0		# count tile recovered
		self.error=len(self.tileList)	# de-count errors
		try:
			for (x,y) in self.tileList:	# loop into tiles list
				fname="%s_%d_%d_%d.%s" % (self.server.name,self.zoom,x,y,self.server.extension)
				fpath=cache.buildpath(fname)
				load=not cache.incache(fpath)
				if load:
					data=None
					tile_url=self.server.getTileUrlFromXY((x,y),self.zoom)
					headers={'User-Agent':kHTTP_User_Agent}
					request=urllib2.Request(tile_url,None,headers)
					try:
						socket.setdefaulttimeout(kHTTP_Time_Out)
						stream=urllib2.urlopen(tile_url)
						header=stream.info()
						content=header.getheaders("Content-Type")
						if len(content)==0 or "text/" in content[0]:
							data=None
							if debug:
								print "error for",tile_url
						else:
							data=stream.read()
						stream.close()
					except urllib2.URLError,e:
						print "URLError:",e
					except urllib2.HTTPError,e:
						print "HTTPError:",e
					except socket.timeout,e:
						print "TimeOut:",e
					if data:	# get the data into an image file
						f=open(fpath,"wb")
						f.write(data)
						f.close()
						self.error-=1
					self.n+=1
				else:
					self.error-=1
				self.done.append((x,y,fname))
		except:
			print "error at tile (%d,%d), z=%d\n" % (x,y,self.zoom),sys.exc_info()
			
def BuildBigMap(server,zoom,(x0,y0),(x1,y1)):
	""" 
		assemble images into a big one using PIL Image classe 
	"""
	wx=x1-x0+1
	wy=y1-y0+1
	bigImage=Image.new("RGBA",(server.tile_size*wx,server.tile_size*wy),"white")
	for x in range(x0,x1+1):
		for y in range(y0,y1+1) :
			fname="%s_%d_%d_%d.%s" % (server.name,zoom,x,y,server.extension)
			fpath=os.path.join(config.k_cache_folder,fname)
			try:
				im=Image.open(fpath)
			except:		
				# no data, build an empty image
				im=Image.new("RGBA",(server.tile_size,server.tile_size),"red")
			box=(server.tile_size*(x-x0),server.tile_size*(y-y0))
			bigImage.paste(im,box)
	fname="z%d_%dx%d_%s.%s" % (zoom,wx,wy,server.name,server.extension)
	bigImage.info['source']=server.name
	bigImage.info['location']=''
	bigImage.info['data']=server.data_copyright
	bigImage.info['map']=server.tile_copyright
	bigImage.info['build']=kHTTP_User_Agent
	bigImage.save(fname)
	
	return fname
		
def LoadServers():
	"""
		Load tiles server data from 'servers.ini' file
		base url, contain several keys :
			[x]	x coordinates
			[y] y coordinates
			[z] zoom
			[q] quadkey for bing server (x,y,z into one value)
			[s] sub-domain level (typically : a,b,c or 0,1,2), empty list if sub-domain
			[a] api-key (if required)
	"""
	list=[]
	servers=ConfigObj("servers.ini")
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
			sd=item['subdomain']
		except:
			sd=None
		try:
			z=item.as_intList('zoom')
		except:
			print "Error: bad zoom (min,max) for",s
			break
		try:
			sz=item.as_intList('size')
		except:
			sz=(config.default_tile_size,config.default_tile_size)
		try:
			dc=item['data']
		except:
			dc=""
		try:
			tc=item['tile']
		except:
			tc=""
		try:
			api=item['api']
		except:
			api=""
		try:
			fmt=item['format']
		except:
			fmt="PNG"
		try:
			mode=item['mode']
		except:
			mode="RGB"
		server=TileServer(s)
		server.setServer(url,sd)
		server.setZoom(z[0],z[1])
		server.setCopyright(tc,dc)
		server.setAPI(api)
		server.setFormat(fmt,mode)
		server.setTileSize(sz[0],sz[1])
		list.append(server)
	return list
	
def Usage():
	print
	print "bigmap usage"
	print "\t-h (--help) : help"
	print "\t-z (--zoom) : set zoom",
	print "\t-b (--box) : setbounding box (left,top,right,bottom)"
	print "\t-l (--location) : set location (longitude,latitude)",
	print "\t-t (--width) : for centered download indicates width and height in longitude,latitude"
	print "\t-c (--cache) : override local tile cache"
	print "\t-s (--server) : set server from name (wildcard is '*'",
	prefix=""
	for s in tile_servers:
		print prefix,s.name,
		prefix=","
	print
	
def ShowServers():
	print
	print "bigmap tile servers list"
	for s in tile_servers:
		print "%s (zoom:%d-%d)" % (s.name,s.min_zoom,s.max_zoom)
		print "\tTile Licence:",s.tile_copyright
		print "\tData Licence:",s.data_copyright
	print
	
def CompareServers(server,box,zoom,use_cache):
	print
	for s in tile_servers:
		print s.name
		
def Coordinates2Box(upleft,downright):
	box=BoundingBox(upleft,downright)
	return box
					
def Do(servers,box,zoom,cache):
	""" 
		Execute the request :
		load map tiles from map servers inside the box at zoom, using or not the cache
	"""
	
	for s in servers:
		(tile0,tile1)=box.convert2Tile(s,zoom)
		x0=int(tile0[0])
		y0=int(tile0[1])
		x1=int(tile1[0])
		y1=int(tile1[1])
		nt=(x1-x0+1)*(y1-y0+1)
		if nt>max_tiles:
			print "** too many tiles : maximum request is %d tile(s)" % max_tiles
			print "\tyour request :",nt
			continue
		if zoom<s.min_zoom or zoom>s.max_zoom:
			print "** zoom %d is not available for %s" % (zoom,s.name)
			print "\tzoom from %d to %d" % (s.min_zoom,s.max_zoom)
			continue
		print "%s : recovering %d tile(s)" % (s.name,nt)
		t0 = time.time()
		
		tlist=[]
		n=0
		if (config.k_multi_thread):
			tileList1=[]
			tileList2=[]
			one=True
			for x in range(x0,x1+1):
				for y in range(y0,y1+1) :
					if one:
						tileList1.append((x,y))
					else:
						tileList2.append((x,y))
					one=not one
			# launch 2 threads to doawnload the tile(s) : asynchronous
			print "\tstart 1st thread"
			t=LoadImageFromURL(s,zoom,tileList1)
			tlist.append(t)
			t.start(cache)
			n=n+1
			print "\tstart 2nd thread"
			t=LoadImageFromURL(s,zoom,tileList2)
			tlist.append(t)
			t.start(cache)
			n=n+1
			print "waiting for completion (%d threads, %d tiles)..." % (n,nt)
		else:
			tileList=[]
			for x in range(x0,x1+1):
				for y in range(y0,y1+1) :
					tileList.append((x,y))		
			# launch 1 thread to doawnload the tile(s) : synchronous
			t=LoadImageFromURL(s,zoom,tileList)
			t.run(cache)
				
		# wait for threads completion
		if len(tlist)>0:
			print len(tlist),"process"
			while len(tlist)>0:
				for t in tlist:
					if not t.isAlive():
						print t.server[0],"done"
						tlist.remove(t)
		
		if config.k_chrono:
			t1 = time.time() - t0
			print "\tdownload time : %.1f seconds, %.1f ips" % (t1,nt/t1)
			t0 = time.time()

		# assemble tiles with PIL
		if t.error/nt<=0.1:
			if t.error>0:
				print "%d errors, force map assembly" % t.error
			print "Assembling %d tile(s) from %s" % (nt,s.name)
			fname=BuildBigMap(s,zoom,(x0,y0),(x1,y1))
			if config.k_chrono:
				t1 = time.time() - t0
				print "\tassembly time : %.1f seconds" % t1
			print "File:",fname
		else:
			print "%d errors, no map generate" % t.error
			
		# remeber credits and licences
		print "\tmap licence  :",s.tile_copyright
		print "\tdata licence :",s.data_copyright
				
		
def main(argv):
	"""
		Main
	"""
	print '-------------------------------------------------'
		
	# 1/ extract and parse command line arguments to determine parameters
	try:
		opts,args=getopt.getopt(argv,"hdcb:l:s:z:t:",["help","display","cache","box=","location=","server=","zoom=","tile=","test="])
	except:
		Usage()
		sys.exit(2)
		
	centered=False
	upleft=Coordinate(config.default_loc0[0],config.default_loc0[1])
	downright=Coordinate(config.default_loc1[0],config.default_loc1[1])
	zoom=config.default_zoom
	server_name=config.default_server
	use_cache=True
	test=False
	err=0
	
	for opt,arg in opts:
		if opt in ("-c","--cache"):
			use_cache=False
		elif opt in ("-l","--location"):
			try:
				list=arg.split(',')
				upleft=Coordinate(float(list[0]),float(list[1]))
				centered=True
			except:
				print "error location must be set as 2 float values",sys.exc_info()
				err+=1
		elif opt in ("-s","--server"):
			server_name=arg
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
				xwidth=float(list[0])
				ywidth=float(list[1])
				centered=True
			except:
				print "error width must be set as 2 int values",sys.exc_info()
				err+=1
		elif opt in ("-d","--display"):
			ShowServers()
		elif opt=="--test":
			server_name=arg
			test=True
		else:
			Usage()
			sys.exit(2)
	
	server=[]
	if server_name=="*":
		server_name=""
	reg=re.compile(server_name)
	for s in tile_servers:
		if "*" in server_name:
			if re.match(reg,s.name):
				server.append(s)
		else:
			if s.name==server_name:
				server.append(s)
	if len(server)==0:
		print "no server known as",server_name
		ShowServers()	
		err+=1
	elif len(server)>1:
		print "%d servers" % len(server)
					
	if err==0:	
		# 2/ do the job
		
		# 2.1/ Check/Create cache
		cache=Cache(config.k_cache_folder,config.k_cache_max_size,config.k_cache_delay)
		cache.setactive(use_cache)
		cache.clear()
		
		if test:
			print "testing server:",server_name
			for s in server:
				s.setZoom(0,21)
			for zoom in range(0,21):
				(xwidth,ywidth)=dtile2ll((2,2),zoom)
				print "zoom %d :" % zoom,(xwidth,ywidth)
				upleft=Coordinate(float(config.test_loc0[0]),float(config.test_loc0[1]))
				downright=Coordinate(upleft.x+xwidth,upleft.y+ywidth)
				upleft=Coordinate(upleft.x-xwidth,upleft.y-ywidth)
				box=Coordinates2Box(upleft,downright)
				print "getting tile for",box,"at zoom %d" % zoom
				Do(server,box,zoom,cache)
		else:
			# 2.2/ convert coordinates to box, if required			
			if (centered):
				downright=Coordinate(upleft.x+xwidth,upleft.y+ywidth)
				upleft=Coordinate(upleft.x-xwidth,upleft.y-ywidth)

			box=Coordinates2Box(upleft,downright)
			print "getting tile for",box,"at zoom %d" % zoom
			
			# 2.3/ lets go
			Do(server,box,zoom,cache)
		
if __name__ == '__main__' :
	tile_servers=LoadServers()
	main(sys.argv[1:])
