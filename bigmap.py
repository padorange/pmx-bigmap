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
	PIL Library : <http://www.pythonware.com/products/pil/>
	
	Licences
	--------
	New-BSD Licence, (c) 2010-2013, Pierre-Alain Dorange
	See ReadMe.txt for data licence for supported servers
	
	History
	-------
	0.1 initial release (september 2010)
	0.2 add openmapquest tiles (june 2011)
		+ troubles with MacOS 10.6 and threads (crash) : used LoadImage in main thread (1 thread only, not optimized)
	0.3 add stamen design maps : watercolor, terrain, toner (january 2013)
	0.4 enhance tiles server handling (march 2013)
		+ debug some platform specific issues
		+ add some CloudMade renders, Acetate and Google
"""

import math
import os.path
import urllib
import threading
import sys
import getopt
import time
import config
from PIL import Image

__version__="0.4"

default_location=(45.6918,-0.3277)		# (latitude, longitude)
default_zoom=14
default_xwidth=5
default_ywidth=5
default_server="mapnik"
default_tile_size=256

kHTTP_User_Agent="bigmap_bot %s" % __version__
    
""" 
	name, server base URL, min zoom, max zoom, coordonate system, copyright 
"""
			
class TileServer():
	"""
		TileServer class : define de tile server and provide simple access to tiles
		Tile Servers (or Slippy Map) use general convention, see : <http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames>
	"""
	def __init__(self,name):
		self.name=name
		self.base_url=""
		self.server_list=None
		self.api_key=""
		self.tile_size=default_tile_size
		self.min_zoom=0
		self.max_zoom=0
		self.format="PNG"
		self.tile_copyright=""
		self.data_copyright=""
		
	def setServer(self,base_url,prefix=None):
		self.base_url=base_url
		self.server_list=prefix
		self.current=0
		
	def setZoom(self,min,max):
		self.min_zoom=min
		self.max_zoom=max
		
	def setAPI(self,key=""):
		self.api_key=key
		
	def setCopyright(self,tile="",data=""):
		self.tile_copyright=tile
		self.data_copyright=data
	
	def getZoom(self):
		return (min_zoom,max_zoom)
	
	def getUrl(self,x,y,z):
		try:
			url=self.base_url
			if url.find("[x]")>=0:
				url=url.replace("[x]","%d" % x)
			else:
				raise
			if url.find("[y]")>=0:
				url=url.replace("[y]","%d" % y)
			else:
				raise
			if url.find("[z]")>=0:
				url=url.replace("[z]","%d" % z)
			else:
				raise
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
		except:
				print "error, malformed server base url",self.base_url,sys.exc_info()
		return url

def ll2tile((latitude,longitude),zoom):
	""" 
		convert a location (longitude, latitude) into a tile position, according to current zoom
		formula from : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
	"""
	lat_rad=math.radians(latitude)
	n=2.0**zoom
	xtile=int((longitude+180.0)/360.0*n)
	ytile=int((1.0-math.log(math.tan(lat_rad)+(1/math.cos(lat_rad)))/math.pi)/2.0*n)
	
	return (xtile,ytile)

class LoadImageFromURL(threading.Thread):
	"""
		Thread for loading tile from a tile server
		Can be used as an asynchronous thread (using start) or synchronous (using run)à
	"""
	def __init__(self,server,zoom,x,y,xw,yw):
		threading.Thread.__init__(self)
		self.server=server
		self.zoom=zoom
		self.x=x
		self.y=y
		self.xw=xw
		self.yw=yw
		self.done=[]
		self.cache=True
		
	def overCache(self,value):
		self.cache=value
		
	def run(self):
		try:
			for xo in range(self.xw):
				for yo in range(self.yw) :
					(x,y)=(self.x+xo-self.xw/2,self.y+yo-self.yw/2)
					fname="%s_%d_%d_%d.png" % (self.server.name,self.zoom,x,y)
					fpath=os.path.join(config.k_cache_folder,fname)
					if not os.path.isfile(fpath) or not self.cache:
						tile_url=self.server.getUrl(x,y,self.zoom)
						print tile_url
						stream=urllib.urlopen(tile_url)
						data=stream.read()
						stream.close()
						f=open(fpath,"wb")
						f.write(data)
						f.close()
					self.done.append((x,y,fname))
		except:
			print "error at tile (%d,%d), z=%d" % (self.x,self.y,self.zoom),sys.exc_info()
			
def BuildBigMap(server,zoom,lx,ly,wx,wy):
	""" 
		assemble images into a big one using PIL Image classe 
	"""
	bigImage=Image.new("RGBA",(server.tile_size*wx,server.tile_size*wy),"white")
	for xo in range(wx):
		for yo in range(wy) :
			try:
				(x,y)=(lx+xo-wx/2,ly+yo-wy/2)
				box=(server.tile_size*xo,server.tile_size*yo)
				fname="%s_%d_%d_%d.png" % (server.name,zoom,x,y)
				fpath=os.path.join(config.k_cache_folder,fname)
				im=Image.open(fpath)
				bigImage.paste(im,box)
			except:		
				print "error on %s\n" % fpath,sys.exc_info()
	fname="z%d_%dx%d_%s.png" % (zoom,wx,wy,server.name)
	bigImage.save(fname,server.format)
	
	return fname
	
def CheckCache():
	""" Just check is cache folder exist, create it if not """
	if not os.path.exists(config.k_cache_folder):
		os.makedirs(config.k_cache_folder)	
	
def InitServers():
	"""
		Prepare tiles server data
		base url, contain several keys :
			[x]	x coordinates
			[y] y coordinates
			[z] zoom
			[s] sub-domain level (typically : a,b,c), empty list if none
			[a] api-key (if required)
	"""
	list=[]
	
	s=TileServer("mapnik")
	s.setServer("http://[s].tile.openstreetmap.org/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(0,18)
	s.setCopyright("(c) mapnik, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("transport")
	s.setServer("http://[s].tile2.opencyclemap.org/transport/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(0,18)
	s.setCopyright("(c) transport by Andy Allan, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("cyclemap")
	s.setServer("http://[s].tile.opencyclemap.org/cycle/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(0,18)
	s.setCopyright("(c) transport by Andy Allan, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("openmapquest")
	s.setServer("http://otile[s].mqcdn.com/tiles/1.0.0/osm/[z]/[x]/[y].png",("1","2","3","4"))
	s.setZoom(0,18)
	s.setCopyright("(c) mapquest, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("openaerial")
	s.setServer("http://otile[s].mqcdn.com/tiles/1.0.0/sat/[z]/[x]/[y].png",("1","2","3","4"))
	s.setZoom(0,11)
	s.setCopyright("(c) mapquest, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("stamen_watercolor")
	s.setServer("http://[s].tile.stamen.com/watercolor/[z]/[x]/[y].png",("a","b","c","d"))
	s.setZoom(0,18)
	s.setCopyright("(c) watercolor by Stamen Design, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("stamen_toner")
	s.setServer("http://[s].tile.stamen.com/toner/[z]/[x]/[y].png",("a","b","c","d"))
	s.setZoom(0,18)
	s.setCopyright("(c) toner by Stamen Design, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
		
	s=TileServer("hikebike")
	s.setServer("http://toolserver.org/tiles/hikebike/[z]/[x]/[y].png")
	s.setZoom(0,18)
	s.setCopyright("(c) hike'n'bike by xxxx, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("opvn")
	s.setServer("http://tile.memomaps.de/tilegen/[z]/[x]/[y].png")
	s.setZoom(0,18)
	s.setCopyright("(c) opvn by memomaps, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("pistemap")
	s.setServer("http://tiles.openpistemap.org/nocontours/[z]/[x]/[y].png")
	s.setZoom(0,17)
	s.setCopyright("(c) xxx, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)

	s=TileServer("shade")
	s.setServer("http://tiles2.openpistemap.org/landshaded/[z]/[x]/[y].png")
	s.setZoom(0,17)
	s.setCopyright("(c) xxx, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("hill")
	s.setServer("http://toolserver.org/~cmarqu/hill/[z]/[x]/[y].png")
	s.setZoom(0,16)
	s.setCopyright("(c) xxx, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("acetate")
	s.setServer("http://a[s].acetate.geoiq.com/tiles/acetate/[z]/[x]/[y].png",("0","1","2","3"))
	s.setZoom(2,18)
	s.setCopyright("(c) esri & stamen","(c) openstreetmap & natural earth")
	list.append(s)
	
	s=TileServer("acetate_roads")
	s.setServer("http://a[s].acetate.geoiq.com/tiles/acetate-roads/[z]/[x]/[y].png",("0","1","2","3"))
	s.setZoom(2,18)
	s.setCopyright("(c) esri & stamen","(c) openstreetmap & natural earth")
	list.append(s)
	
	s=TileServer("acetate_background")
	s.setServer("http://a[s].acetate.geoiq.com/tiles/acetate-bg/[z]/[x]/[y].png",("0","1","2","3"))
	s.setZoom(2,18)
	s.setCopyright("(c) esri & stamen","(c) openstreetmap & natural earth")
	list.append(s)
	
	s=TileServer("bluemarble")
	s.setServer("http://s3.amazonaws.com/com.modestmaps.bluemarble/[z]-r[y]-c[x].jpg")
	s.setZoom(2,9)
	s.setCopyright("public domain")
	list.append(s)
	
	s=TileServer("cloudmade_standard")
	s.setServer("http://[s].tile.cloudmade.com/[a]/1/256/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(2,18)
	s.setAPI(config.cloudmade_API)
	s.setCopyright("(c) standard by CloudMade, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("cloudmade_fineline")
	s.setServer("http://[s].tile.cloudmade.com/[a]/2/256/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(2,18)
	s.setAPI(config.cloudmade_API)
	s.setCopyright("(c) standard by CloudMade, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("cloudmade_fresh")
	s.setServer("http://[s].tile.cloudmade.com/[a]/997/256/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(2,18)
	s.setAPI(config.cloudmade_API)
	s.setCopyright("(c) standard by CloudMade, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("cloudmade_tourism")
	s.setServer("http://[s].tile.cloudmade.com/[a]/1155/256/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(2,18)
	s.setAPI(config.cloudmade_API)
	s.setCopyright("(c) standard by CloudMade, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("cloudmade_thin")
	s.setServer("http://[s].tile.cloudmade.com/[a]/1/256/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(2,18)
	s.setAPI(config.cloudmade_API)
	s.setCopyright("(c) standard by CloudMade, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("cloudmade_thin")
	s.setServer("http://[s].tile.cloudmade.com/[a]/1/256/[z]/[x]/[y].png",("a","b","c"))
	s.setZoom(2,18)
	s.setAPI(config.cloudmade_API)
	s.setCopyright("(c) standard by CloudMade, licence CC-BY-SA","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("arcgis_topo")
	s.setServer("http://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/[z]/[y]/[x].png")
	s.setZoom(0,13)
	s.setCopyright("(c) esri.com, licence CC-BY-SA-NC","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("arcgis_imagery")
	s.setServer("http://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/[z]/[y]/[x].png")
	s.setZoom(0,13)
	s.setCopyright("(c) esri.com, licence CC-BY-SA-NC","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("arcgis_terrain")
	s.setServer("http://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Reference_Overlay/MapServer/tile/[z]/[y]/[x].png")
	s.setZoom(0,13)
	s.setCopyright("(c) esri.com, licence CC-BY-SA-NC","(c) openstreetmap.org and contributors, licence ODbL")
	list.append(s)
	
	s=TileServer("google_road")
	s.setServer("http://mt[s].google.com/vt/x=[x]&y=[y]&z=[z]",("0","1","2","3"))
	s.setZoom(2,20)
	s.setCopyright("(c) google","(c) google")
	list.append(s)
	
	s=TileServer("google_aerial")
	s.setServer("http://khm[s].google.com/kh/v=45&x=[x]&y=[y]&z=[z]",("0","1","2","3"))
	s.setZoom(2,18)
	s.setCopyright("(c) google","(c) google")
	list.append(s)
	
	s=TileServer("bing_road")
	s.setServer("http://r[s].ortho.tiles.virtualearth.net/tiles/r[M].png?g=90&shading=hill",("0","1","2","3"))
	s.setZoom(2,19)
	s.setCopyright("(c) microsoft road","(c) microsoft road")
	list.append(s)
	
	s=TileServer("mapbox_landsat")
	s.setServer("http://a.tiles.mapbox.com/v3/examples.map-2k9d7u0c/[z]/[x]/[y].png")
	s.setZoom(2,12)
	s.setCopyright("(c) mapbox, landsat")
	list.append(s)
	
	return list
	
def Usage():
	print
	print "bigmap usage"
	print "\t-h (--help) : help"
	print "\t-l (--location) : set location (latitude, longitude)",
	print "\t-z (--zoom) : set zoom",
	print "\t-t (--width) : set tile width"
	print "\t-c (--cache) : override local tile cache"
	print "\t-s (--server) : set server from :",
	prefix=""
	for s in tile_servers:
		print prefix,s.name,
		prefix=","
	print
	
def ShowServers():
	print
	print "bigmap tile serves list"
	for s in tile_servers:
		print "%s (zoom:%d-%d)" % (s.name,s.min_zoom,s.max_zoom)
		print "\tTile Licence:",s.tile_copyright
		print "\tData Licence:",s.data_copyright
	print
		
def main(argv):
	"""
		Main
	"""
	print '-------------------------------------------------'
		
	# 1/ extract and parse command line arguments to determine parameters
	try:
		opts,args=getopt.getopt(argv,"hdcl:s:z:t:",["help","display","cache","location=","server=","zoom=","tile="])
	except:
		Usage()
		sys.exit(2)
		
	location=default_location
	zoom=default_zoom
	xwidth=default_xwidth
	ywidth=default_ywidth
	server_name=default_server
	use_cache=True
	
	for opt,arg in opts:
		if opt in ("-c","--cache"):
			use_cache=False
		elif opt in ("-l","--location"):
			try:
				list=arg.split(',')
				location=(float(list[0]),float(list[1]))
			except:
				print "error location must be set as 2 float values",sys.exc_info()
		elif opt in ("-s","--server"):
			server_name=arg
		elif opt in ("-z","--zoom"):
			zoom=int(arg)
		elif opt in ("-t","--tile"):
			try:
				list=arg.split(',')
				xwidth=int(list[0])
				ywidth=int(list[1])
			except:
				print "error width must be set as 2 int values",sys.exc_info()
		elif opt in ("-d","--display"):
			ShowServers()
		else:
			Usage()
			sys.exit(2)
			
	# 2/ do the job
	CheckCache()
	
	print "getting tile for (latitude:%.4f, longitude:%.4f) at zoom %d" % (location[0],location[1],zoom)

	tile=ll2tile(location,zoom)

	tlist=[]
	n=0
	nt=xwidth*ywidth
	
	# find the right server parameter, according to "server name"
	server=None
	for s in tile_servers:
		if server_name==s.name:
			server=s
			break
	if server:		
		if zoom>=server.min_zoom and zoom<=server.max_zoom:
			print "\tget %d tile(s) from %s" % (nt,server.name)
			print "\tmap licence  :",server.tile_copyright
			print "\tdata licence :",server.data_copyright
			
			if config.k_chrono:
				t0 = time.time()
				
			if (config.k_multi_thread):
				# launch 2 threads to doawnload the tile(s) : asynchronous
				print "\tstart 1st thread"
				t=LoadImageFromURL(server,zoom,tile[0],tile[1],xwidth,ywidth)
				t.overCache(use_cache);
				tlist.append(t)
				t.start()
				n=n+1
				print "\tstart 2nd thread"
				t=LoadImageFromURL(server,zoom,tile[0]+2,tile[1],xwidth,ywidth)
				t.overCache(use_cache);
				tlist.append(t)
				t.start()
				n=n+1
				print "waiting for completion (%d threads, %d tiles)..." % (n,nt)
			else:
				# launch 1 thread to doawnload the tile(s) : synchronous
				t=LoadImageFromURL(server,zoom,tile[0],tile[1],xwidth,ywidth)
				t.overCache(use_cache);
				print "waiting for completion (%d threads, %d tiles)..." % (n,nt)
				t.run()
			
			# wait for threads completion
			print len(tlist),"process"
			while len(tlist)>0:
				for t in tlist:
					if not t.isAlive():
						print t.server[0],"done"
						tlist.remove(t)
			
			if config.k_chrono:
				t1 = time.time() - t0
				print "\tdownload time : %.1f seconds, %.1f fps" % (t1,nt/t1)
				t0 = time.time()

			# assemble tiles with PIL
			print "assembling %d tile(s) from %s" % (nt,server.name)
			fname=BuildBigMap(server,zoom,tile[0],tile[1],xwidth,ywidth)
					
			if config.k_chrono:
				t1 = time.time() - t0
				print "\tassembly time : %.1f seconds" % t1
			print "Done, see file",fname
		else:
			print "zoom %d is not available for %s" % (zoom,server.name)
			print "\tzoom from %d to %d" % (server.min_zoom,server.max_zoom)
	else:
		print "no server known as",server_name
		ShowServers()
		
if __name__ == '__main__' :
	tile_servers=InitServers()
	main(sys.argv[1:])
