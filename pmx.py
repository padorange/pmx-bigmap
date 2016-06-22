#!/usr/bin/env python
# -*- coding: utf-8 -*-

# == projet description =====================================
__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"
__copyright__="Copyright 2016, Pierre-Alain Dorange"
__license__="BSD"
__version__="1.0a2"
__application__="Python Map eXplorer (pmx)"

# debug tags
_debug_idle=False
_debug_gui=False
_debug_coord=False
_debug_sql=False
_debug_chrono=False
_debug_offscreen=False

""" pmx.py (Python Map eXplorer)
----------------------------------------------------------------------------------------
A Map Explorer software based on TMS online services (slippymap)
pmx rely on 
	- bigmap.py library (included)
	- Tkinter (most often included into python)
	- PIL or Pillow library (not included, require seperate install)

usage: python pmx.py

See ReadMe.txt for detailed instructions
See bigmap.py for detail on TMS downloads.	
	
-- Requirements ------------------------------------------------------------------------
	Python 2.5 / 2.7
	Tkinter (include with python) for cross-platform GUI
	PIL or Pillow Library : <http://www.pythonware.com/products/pil/>
	ConfigObj : modified ConfigObj 4 <http://www.voidspace.org.uk/python/configobj.html>
	
-- Licences ----------------------------------------------------------------------------
	New-BSD Licence, (c) 2010-2016, Pierre-Alain Dorange
	See ReadMe.txt for instructions
	
-- References --------------------------------------------------------------------------
	How web map works : https://www.mapbox.com/help/how-web-maps-work/
	TileMap Maths : http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
	EPSG:3857 projection : https://en.wikipedia.org/wiki/Web_Mercator
	Quadkey for Bing : http://www.web-maps.com/gisblog/?m=200903
	Longitude : https://en.wikipedia.org/wiki/Longitude
	Latitude : https://en.wikipedia.org/wiki/Latitude
	
-- History -----------------------------------------------------------------------------
	1.0a1 february 2016 : initial alpha
	1.0a2 march 2016 : 
		add SQLite3 dababase to store config (location, zoom and map)
		optimize overlay displaying
		optimize loading (adding a ram cache for bigmap.py)
"""
# == Standard Library =======================================
import os,sys,time
import threading,Queue
import sqlite3
import Tkinter, tkFileDialog, tkMessageBox	# Tkinter (TK/TCL for Python) : Simple standard GUI (no-OS dependant)

# == Special Library (need seperate install) =================
from PIL import Image,ImageDraw,ImageTk		# Image manipulation library

# == Local library ==========================================
import config
import bigmap

# == Constants & Globals ==============================================
k_frame=20

# trick to made utf-8 default encoder/decoder (python 2.x)
reload(sys)
sys.setdefaultencoding('utf8')

# -- GUI classes (using Tkinter) ---------------------

class TMap(Tkinter.Canvas):
	""" the map canvas :
			refresh (True) : update the complete map (zoom or server change)
			update (True) : update some tiles (scroll)
			mapOffscreen : the offscreen full image for map (larger than viewed)
			overlayOffscreen : the offscreen full image for overlay (larger than viewed)
			tkOffscreen : the tk version of the offsceen image (mix map+overlay), to allow tkinter to handle draw
	"""
	def __init__(self,window,width=800,height=600,date=None,cache=None):
		Tkinter.Canvas.__init__(self,window,width=width,height=height,relief=Tkinter.RIDGE,background="#fff0d4")
		self.parent=window
		self.width=width
		self.height=height
		self.item=None
		self.tkOffscreen=None
		self.mapOffscreen=bigmap.BigMap()
		self.overlayOffscreen=bigmap.BigMap(overlay=True)
		self.loadingImg=window.loadingImg
		self.mapServer=None
		self.overlayServer=None
		self.zoom=0
		self.location=None
		(self.xmin,self.ymin)=(0,0)
		(self.xmax,self.ymax)=(0,0)
		(self.offsetx,self.offsety)=(0,0)
		self.cache=cache
#		self.setMapServer(server)
#		self.setOverlayServer(overlay)
#		self.setLocation(location,zoom)
		self.date=date
		self.loading=False
		self.bind("<ButtonPress-1>",self.onClicDown)
		self.bind("<ButtonRelease-1>",self.onClicUp)
		self.bind("<MouseWheel>",self.onMouseWheel)
		self.bind("<Double-Button-1>",self.onDoubleClic)
		# create the task queue : 2 queue(s) : work (task to be done) / result (task results)
		self.work_queue=Queue.Queue()
		self.result_queue=Queue.Queue()
		self.refresh=True
		self.clock=0.0
		self.clock_nb=0
		self.clock_task=False
		self.fps_clock=0.0
		self.fps=0
		if _debug_offscreen:
			self.frame=0
			
		self.after(0,self.idle)

	def onClicDown(self,event):
		""" Handle clic : first clic active drag motion """
		event.widget.bind ("<Motion>", self.onClicDrag)
		self.clicLoc=(event.x,event.y)
		self.originLoc=(event.x,event.y)
		if _debug_gui: print "clic @",self.clicLoc
		
	def onClicUp(self,event):
		""" handle clic release : stop drag motion """
		event.widget.unbind ("<Motion>")
		(mx,my)=(event.x-self.originLoc[0],event.y-self.originLoc[1])
		(mtx,mty)=(1.0*mx/self.mapServer.tile_size,1.0*my/self.mapServer.tile_size)
		(x,y)=self.location.convert2Tile(self.zoom)
		if _debug_gui: print "release :", (mx,my),(mtx,mty)
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "move (pixels) : ",(mx,my)
			print "move (tiles) : ",(mtx,mty)
		self.location.convertFromTile((x-mtx,y-mty),self.zoom)
		self.parent.config.set('LONGITUDE',self.location.lon)
		self.parent.config.set('LATITUDE',self.location.lat)
		self.refresh=True
	
	def onClicDrag(self,event):
		""" handle drag (clic maintain and mouse moved) : 
			drag the map into the view (without loading) """
		(mx,my)=(event.x-self.clicLoc[0],event.y-self.clicLoc[1])
		(self.offsetx,self.offsety)=(self.offsetx-mx,self.offsety-my)
		self.updateMap()
		self.clicLoc=(event.x,event.y)
		if _debug_gui: print "drag :",mov
		
	def onMouseWheel(self,event):
		""" handle mouse wheel scroll : zoom in/out """
		if event.delta<0:
			self.setZoom(self.zoom-1)
		else:
			self.setZoom(self.zoom+1)
	
	def onDoubleClic(self,event):
		""" handle double clic : move to location """
		(mx,my)=(event.x-self.winfo_reqwidth()/2,event.y-self.winfo_reqheight()/2)
		(mtx,mty)=(1.0*mx/self.mapServer.tile_size,1.0*my/self.mapServer.tile_size)
		(x,y)=self.location.convert2Tile(self.zoom)
		if _debug_gui: print "release :", (mx,my),(mtx,mty)
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "move (pixels) : ",(mx,my)
			print "move (tiles) : ",(mtx,mty)
		self.location.convertFromTile((x+mtx,y+mty),self.zoom)
		self.parent.config.set('LONGITUDE',self.location.lon)
		self.parent.config.set('LATITUDE',self.location.lat)
		self.refresh=True
			
	def setLocation(self,location,zoom=None):
		""" define a new location (with optional zoom) for the map and store default """
		if zoom:
			self.setZoom(zoom)
		if self.location!=location:
			self.location=location
			self.parent.config.set('LONGITUDE',self.location.lon)
			self.parent.config.set('LATITUDE',self.location.lat)
			self.refresh=True
		
	def setZoom(self,zoom):
		""" define a new zoom for the map and store default """
		(zmmin,zmmax)=self.mapServer.getZoom()
		if self.overlayServer:
			(zomin,zomax)=self.overlayServer.getZoom()
			zmin=max(zmmin,zomin)
			zmax=min(zmmax,zomax)
		else:
			(zmin,zmax)=(zmmin,zmmax)
		if zoom<zmin:
			z=zmin
		if zoom>zmax:
			z=zmax
		else:
			z=zoom
		if z!=self.zoom:
			self.zoom=z
			self.parent.setZoomText("z=%d" % self.zoom)
			self.parent.config.set('ZOOM',self.zoom)
			self.refresh=True
		
	def setMapServer(self,map_server):
		""" define a new map server and store default (+update zoom) """
		if self.mapServer!=map_server:
			self.mapServer=map_server
			self.setZoom(self.zoom)
			if self.mapServer:
				mapname=self.mapServer.name
			else:
				mapname=""
			self.xdtile=int(0.5*self.width/map_server.size_x)+1
			self.ydtile=int(0.5*self.height/map_server.size_y)+1
			self.parent.config.set('MAP',mapname)
			self.refresh=True
		
	def setOverlayServer(self,overlay_server):
		""" define a new overlay server for the map from its name and store default (+update zoom) """
		if self.overlayServer!=overlay_server:
			self.overlayServer=overlay_server
			self.setZoom(self.zoom)
			if self.overlayServer:
				mapname=self.overlayServer.name
			else:
				mapname=""
			self.parent.config.set('OVERLAY',mapname)
			self.refresh=True
		
	def idle(self):
		""" Handle updates : called when idle """
		old_status=self.loading
		if self.refresh:
			self.refreshOffscreen()
			force_update=True
			if _debug_idle: print "refresh"
		else:
			force_update=False
		if self.work_queue.empty():
			self.loading=True
			if _debug_chrono:
				if self.clock_task:
					self.clock=time.clock()-self.clock
					if self.clock>0.0:
						print "download tiles: %d / speed: %.2f tps" % (self.clock_nb,self.clock_nb/self.clock)
					self.clock_nb=0
					self.clock_task=False
					self.clock=0
					print "fps: %.2f fps" % (self.fps/self.fps_clock)
					self.fps=0
					self.fps_clock=0.0
		else:
			self.loading=False
		if self.loading!=old_status:
			force_update=True
			if self.loading:
				status=""
			else:
				status=" (loading)"
			self.parent.setStatus(status)
		if _debug_idle: print "\twork:",self.work_queue.qsize(),"\tresult:",self.result_queue.qsize()
		if not(self.result_queue.empty()) or force_update:
			self.updateMap()
			if _debug_idle: print "update"
		self.after(k_frame,self.idle)
		
	def refreshOffscreen(self):
		""" refresh the map : create offscren and launch tiles loading (asynchronous)
			the offscren contain a "map" and an "overlay" (optionnal)
			map elements (tiles) are loaded in priority
		"""
		(x,y)=self.location.convert2Tile(self.zoom)
		(self.xmin,self.ymin)=(int(x)-self.xdtile,int(y)-self.ydtile)
		(self.xmax,self.ymax)=(int(x)+self.xdtile,int(y)+self.ydtile)
		self.mapOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
		self.overlayOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
		sz=(self.winfo_reqwidth(),self.winfo_reqheight())
		(self.offsetx,self.offsety)=(int(self.mapServer.tile_size*(x-int(x)+2))-sz[0]/2,int(self.mapServer.tile_size*(y-int(y)+2))-sz[1]/2)
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "tilebox:", (self.xmin,self.ymin),(self.xmax,self.ymax)
			print "map size:",sz
			print "offset (pixels) : ",(self.offsetx,self.offsety)
		if _debug_chrono:
			self.clock=time.clock()
			self.clock_task=True
			self.clock_nb=self.clock_nb+(self.xmax-self.xmin+1)*(self.ymax-self.ymin+1)
			if self.overlayServer:
				self.clock_nb*self.clock_nb*2
		for x in range(self.xmin,self.xmax+1):
			for y in range(self.ymin,self.ymax+1) :
				self.work_queue.put((x,y,self.zoom,self.mapServer,self.date,self.cache))
		if self.overlayServer:
			for x in range(self.xmin,self.xmax+1):
				for y in range(self.ymin,self.ymax+1) :
					self.work_queue.put((x,y,self.zoom,self.overlayServer,self.date,self.cache))
		# launch the task queue
		if (bigmap.config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queues
			for i in range(bigmap.config.k_nb_thread):
				task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue)
				task.start()
		else:	# for synchronous : run a single task until queue is empty
			task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue)
			task.run()
		self.refresh=False
		
	def updateMap(self):
		""" assemble tiles images (as soon as they were ready) with PIL into a big offscreen image
		"""
		# handle ended jobs
		error=0
		while not(self.result_queue.empty()):
			error=error+self.result_queue.get()
			self.result_queue.task_done()
		if error>0:
			print "%d errors, force map assembly" % error
		# create the offscreen and assemble into it
		if _debug_chrono: 
			self.fps_clock=self.fps_clock-time.clock()
		if self.mapServer:
			self.mapOffscreen.setServer(self.mapServer,self.zoom,self.date)
			self.mapOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
			self.mapOffscreen.build()
			map_img=self.mapOffscreen.getImg()
			if self.overlayServer:
				self.overlayOffscreen.setServer(self.overlayServer,self.zoom,self.date)
				self.overlayOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
				self.overlayOffscreen.build()
				if _debug_offscreen:
					map_img.save("debug_%05d_base_map.%s" % (self.frame,self.mapServer.extension))
				layer=self.overlayOffscreen.getImg()
				map_img.paste(layer,mask=layer)
				if _debug_offscreen:
					layer.save("debug_%05d_layer.%s" % (self.frame,self.overlayServer.extension))
					map_img.save("debug_%05d_final_map.%s" % (self.frame,self.mapServer.extension))
					self.frame=self.frame+1
			# loading indicator
			if not self.loading:
				(iw,ih)=self.loadingImg.size
				(x,y)=((self.winfo_reqwidth()-iw)/2+self.offsetx,(self.winfo_reqheight()-ih)/2+self.offsety)
				map_img.paste(self.loadingImg,(x,y),mask=self.loadingImg)
			# create TK image and copy map+overlay into it
			self.tkOffscreen=ImageTk.PhotoImage(map_img)
			self.delete(self.item)
			self.item=self.create_image(-self.offsetx,-self.offsety,image=self.tkOffscreen,anchor=Tkinter.NW)
		if _debug_chrono: 
			self.fps_clock=self.fps_clock+time.clock()
			self.fps=self.fps+1

class AppConfig():
	""" Handle default config (saved in SQLite database)
		- save/load config into a SQLite database
		- accessor for the App to the config
	"""
	def __init__(self,dbPath):
		if _debug_sql:
			print "pmx database:",dbPath
		map=""
		for s in bigmap.tile_servers:
			if s.name==bigmap.config.default_server:
				map=s.name
				break
		overlay=""
		self.params={	'VERSION':('str_value','1'),
						'MAP':('str_value',map),
						'OVERLAY':('str_value',overlay),
						'LONGITUDE':('real_value',(bigmap.config.default_loc0[0]+bigmap.config.default_loc1[0])/2),
						'LATITUDE':('real_value',(bigmap.config.default_loc0[1]+bigmap.config.default_loc1[1])/2),
						'ZOOM':('int_value',bigmap.config.default_zoom)}
		self.sql=sqlite3.connect(dbPath)
	
	def get(self,id):
		try:
			(field,value)=self.params[id]
		except:
			print "param:",id,"do not exist"
			print sys.exc_info()
			value=None
		return value
	
	def set(self,id,value):
		try:
			(field,old)=self.params[id]
			if (old!=value):
				self.params[id]=(field,value)
				self.save1Param(id,value)
		except:
			print "param:",id,"do not exist"
			print sys.exc_info()
	
	def load1Param(self,id,c=None):
		""" load 1 parameter from database (sql cursor is optionnal) """
		if not c:
			c=self.sql.cursor()
			close=True
		else:
			close=False
		try:
			(field,value)=self.params[id]
			sql_cmd="SELECT %s from params WHERE id='%s';" % (field,id)
			if _debug_sql:
				print sql_cmd
			c.execute(sql_cmd)
			data=c.fetchone()
			if _debug_sql:
				print "\tresult:",data
			if data==None or len(data)==0:
				sql_cmd="INSERT INTO params (id,"+field+") VALUES ('"+id+"','"+str(value)+"');"
				if _debug_sql:
					print sql_cmd
				c.execute(sql_cmd)
				self.sql.commit()
			else:
				value=data[0]
				self.params[id]=(field,value)
		except:
			value=None
			print "param:",id,"do not exist"
			print sys.exc_info()
		if close :
			c.close()
		return value
		
	def save1Param(self,id,value,c=None):
		""" save 1 parameter from database (sql cursor is optionnal) """
		if not c:
			c=self.sql.cursor()
			close=True
		else:
			close=False
		try:
			(field,value)=self.params[id]
			sql_cmd="UPDATE params SET "+field+"='"+str(value)+"' WHERE id='"+id+"';"
			if _debug_sql:
				print sql_cmd
			c.execute(sql_cmd)
			self.sql.commit()
			if close :
				c.close()
		except:
			print "param:",id,"do not exist"
			print sys.exc_info()
		
	def load(self):
		cursor=self.sql.cursor()
		# create table if not allready done
		sql_cmd="CREATE TABLE IF NOT EXISTS params (id TEXT PRIMARY KEY,str_value TEXT,int_value INTEGER,real_value REAL);"
		if _debug_sql:
			print sql_cmd
		cursor.execute(sql_cmd)
		self.sql.commit()
		# load params
		for k in self.params.keys():
			self.load1Param(k,cursor)
		cursor.close()
		mapname=self.get("MAP")
		for s in bigmap.tile_servers:
			if s.name==mapname:
				return
		mapname=""
		for s in bigmap.tile_servers:
			if s.name==bigmap.config.default_server:
				mapname=s.name
				break
		if len(mapname)==0:
			mapname=bigmap.tile_servers[0]
		self.set('MAP',mapname)
		
	def save(self):
		cursor=self.sql.cursor()
		for k in self.params.keys():
			self.save1Param(k,cursor)
		cursor.close()
	
class main_gui(Tkinter.Frame):
	""" display the main window : map exploxer
	"""
	def __init__(self,window,cfg=None):
		Tkinter.Frame.__init__(self,window,width=800,height=600)
		
		self.config=cfg
		self.clock=time.clock()
		self.loadingImg=Image.open(config.loadingImgPath)
		
		# default map config
		self.currentMap=None
		self.currentOverlay=None
		map=self.config.get('MAP')
		for s in bigmap.tile_servers:
			if s.name==map:
				self.currentMap=s
				break
		overlay=self.config.get('OVERLAY')
		for s in bigmap.tile_servers:
			if s.name==overlay:
				self.currentOverlay=s
				break
		lon=self.config.get('LONGITUDE')
		lat=self.config.get('LATITUDE')
		dl=bigmap.Coordinate(lon,lat)
		dz=self.config.get('ZOOM')
		
		# create the cache handler
		self.cache=bigmap.Cache(bigmap.config.cachePath,bigmap.config.k_cache_max_size,bigmap.config.k_cache_delay)
		self.cache.setactive(True)
		self.cache.clear()
		print "cache size:",self.cache
		
		# create Tkinter variables
		self.serverInfos=Tkinter.StringVar()
		self.serverRights=Tkinter.StringVar()
		self.setServerText(self.currentMap,self.currentOverlay)
		self.statusInfos=Tkinter.StringVar()
		self.statusInfos.set(str(self.cache))
		self.zoomInfos=Tkinter.StringVar()
		self.setZoomText("")
		
		# create Widgets
		self.map=TMap(self,width=800,height=600,cache=self.cache,date=None)
		self.zoomTxt=Tkinter.Label(self,textvariable=self.zoomInfos,anchor=Tkinter.W,justify=Tkinter.CENTER,font=("Arial",10))
		self.statusTxt=Tkinter.Label(self,textvariable=self.statusInfos,anchor=Tkinter.W,justify=Tkinter.LEFT,font=("Arial",10))
		self.infoLabel=Tkinter.Label(self,text="Informations",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.infoTxt=Tkinter.Message(self,textvariable=self.serverInfos,anchor=Tkinter.W,justify=Tkinter.LEFT,width=350,font=("Arial",10))
		self.rightsLabel=Tkinter.Label(self,text="Legals",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.rightsTxt=Tkinter.Message(self,textvariable=self.serverRights,anchor=Tkinter.W,justify=Tkinter.LEFT,width=350,font=("Arial",10))
		self.mListLabel=Tkinter.Label(self,text="Map",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.mScroll=Tkinter.Scrollbar(self,orient=Tkinter.VERTICAL)
		self.mList=Tkinter.Listbox(self,width=28,height=20,relief=Tkinter.RIDGE,yscrollcommand=self.mScroll.set,font=("Arial",11))
		self.oListLabel=Tkinter.Label(self,text="Overlay",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.oScroll=Tkinter.Scrollbar(self,orient=Tkinter.VERTICAL)
		self.oList=Tkinter.Listbox(self,width=28,height=10,relief=Tkinter.RIDGE,yscrollcommand=self.oScroll.set,font=("Arial",11))
		self.bZIn=Tkinter.Button(self,text="+",command=self.doZoomIn)
		self.bZOut=Tkinter.Button(self,text="-",command=self.doZoomOut)
		
		# link widgets with function and/or other widget (scrollers)
		self.mList.bind("<<ListboxSelect>>",self.on_map_select)
		self.mScroll.configure(command=self.mList.yview)
		self.oList.bind("<<ListboxSelect>>",self.on_overlay_select)
		self.oScroll.configure(command=self.oList.yview)
		self.map.bind("<Configure>",self.resize)
		
		# load data into List widgets
		self.loadList()
		
		# define the grid configuration (using gridmanager)
		self.grid(sticky=Tkinter.N+Tkinter.S+Tkinter.W+Tkinter.E,padx=5,pady=5)
		top=self.winfo_toplevel()
		top.columnconfigure(0,weight=1)
		top.rowconfigure(0,weight=1)
		self.columnconfigure(1,weight=1)
		self.rowconfigure(2,weight=1)
		self.rowconfigure(4,weight=1)
		# Use the Grid manager to fit all the widgets in the window at there respected position
		self.statusTxt.grid(row=0,column=1,sticky=Tkinter.NW,padx=2,pady=2)
		self.map.grid(row=1,column=1,rowspan=4,columnspan=2,padx=2,pady=2)
		self.mListLabel.grid(row=1,column=3,sticky=Tkinter.NW,padx=2,pady=2)
		self.mList.grid(row=2,column=3,sticky=Tkinter.N+Tkinter.S,padx=0,pady=2)
		self.mScroll.grid(row=2,column=4,sticky=Tkinter.N+Tkinter.S,padx=0,pady=2)
		self.oListLabel.grid(row=3,column=3,sticky=Tkinter.NW,padx=2,pady=2)
		self.oList.grid(row=4,column=3,sticky=Tkinter.N+Tkinter.S,padx=0,pady=2)
		self.oScroll.grid(row=4,column=4,sticky=Tkinter.N+Tkinter.S,padx=0,pady=2)
		self.infoLabel.grid(row=5,column=1,sticky=Tkinter.NW,padx=2,pady=2)
		self.infoTxt.grid(row=6,column=1,sticky=Tkinter.NW,padx=2,pady=2)
		self.rightsLabel.grid(row=5,column=2,sticky=Tkinter.NW,padx=2,pady=2)
		self.rightsTxt.grid(row=6,column=2,sticky=Tkinter.NW,padx=2,pady=2)
		self.zoomTxt.grid(row=0,column=0,padx=2,pady=2)
		self.bZIn.grid(row=1,column=0,sticky=Tkinter.NW,padx=2,pady=2)
		self.bZOut.grid(row=2,column=0,sticky=Tkinter.NW,padx=2,pady=2)

		self.map.setMapServer(self.currentMap)
		self.map.setOverlayServer(self.currentOverlay)
		self.map.setLocation(dl,dz)
		
		print "Map:",self.map.grid_info()
		print "Map size:",self.map.winfo_width(),self.map.winfo_height()
		print "Map size:",self.map.winfo_reqwidth(),self.map.winfo_reqheight()
		print "Map size:",self.size()
		print "Self:",self.grid_info()
		print "Self grid:",self.grid_size()
		print "Row 1:",self.grid_slaves(row=1)
		print "Column 1:",self.grid_slaves(column=1)
		
	def quit(self):
		self.config.save()
		Tkinter.Frame.quit(self)
		
	def loadList(self):
		self.oList.insert(Tkinter.END,"None")
		self.overlays=[None]
		self.maps=[]
		mIndex=-1
		oIndex=-1
		for s in bigmap.tile_servers:
			title="%s (%d-%d)" % (s.name,s.min_zoom,s.max_zoom)
			if s.type=="overlay":
				self.oList.insert(Tkinter.END,title)
				self.overlays.append(s)
				if self.currentOverlay:
					if s.name==self.currentOverlay.name:
						oIndex=len(self.overlays)-1
						if _debug_gui:
							print "default overlay:",oIndex,s.name
			else:
				self.mList.insert(Tkinter.END,title)
				self.maps.append(s)
				if self.currentMap:
					if s.name==self.currentMap.name:
						mIndex=len(self.maps)-1
						if _debug_gui:
							print "default map:",mIndex,s.name
		self.mList.selection_set(mIndex)
		self.mList.see(mIndex)
		self.oList.selection_set(oIndex)
		self.oList.see(oIndex)
		
	def resize(self,event):
		print "-- RESIZED ----------------"
		print "event size:",event.width,event.height
		print "widget size:",event.widget.size()
		print "widget real size:",event.widget.winfo_width(),event.widget.winfo_height()
		print "widget request size:",event.widget.winfo_reqwidth(),event.widget.winfo_reqheight()
	
	def on_map_select(self,event):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			if _debug_gui: print "select:",id
			self.currentMap=self.maps[id]
		else:
			id=-1
			if _debug_gui: print "noselect:"
			self.currentMap=None
		if _debug_gui: print "\tmap:",self.currentMap
		self.map.setMapServer(self.currentMap)
		self.setServerText(self.currentMap,self.currentOverlay)
	
	def on_overlay_select(self,event):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			if _debug_gui: print "select:",id
			self.currentOverlay=self.overlays[id]
		else:
			id=-1
			if _debug_gui: print "noselect:"
			self.self.currentOverlay=None
		if _debug_gui: print "\tmap:",self.currentOverlay
		self.map.setOverlayServer(self.currentOverlay)
		self.setServerText(self.currentMap,self.currentOverlay)
		
	def doZoomIn(self):
		self.map.setZoom(self.map.zoom+1)
	
	def doZoomOut(self):
		self.map.setZoom(self.map.zoom-1)
		
	def setZoomText(self,txt):
		self.zoomInfos.set(txt)
	
	def setStatus(self,status=""):
		if time.clock()>self.clock:
			self.cacheStrSize=str(self.cache)
			self.clock=time.clock()+2.0
		self.statusInfos.set("Status: "+self.cacheStrSize+status)
		
	def setServerText(self,server=None,overlay=None):
		if not(server):
			server=self.currentMap
		if not(overlay):
			overlay=self.currentOverlay
		if server:
			try:
				infoStr="%s (zoom:%d-%d)" % (server.name,server.min_zoom,server.max_zoom)
				if len(server.provider)>0 :
					infoStr=infoStr+" by %s" % server.provider
				if len(server.familly)>0 :
					infoStr=infoStr+"\nfamilly : %s" % server.familly
				if len(server.description)>0 :
					infoStr=infoStr+"\n%s" % server.description
				rightsStr="Tile Licence: %s\nData Licence: %s" % (server.tile_copyright,server.data_copyright)
			except:
				print "error with currentMap:",server
				print sys.exc_info()
			if overlay:
				try:
					infoStr=infoStr+"\n----------------------"
					infoStr=infoStr+"\n%s (zoom:%d-%d)" % (overlay.name,overlay.min_zoom,overlay.max_zoom)
					if len(overlay.provider)>0 :
						infoStr=infoStr+" by %s" % overlay.provider
					if len(overlay.familly)>0 :
						infoStr=infoStr+"\nfamilly : %s" % overlay.familly
					if len(overlay.description)>0 :
						infoStr=infoStr+"\n%s" % overlay.description
					rightsStr=rightsStr+"\n------------------------"
					rightsStr=rightsStr+"\nTile Licence: %s\nData Licence: %s" % (overlay.tile_copyright,overlay.data_copyright)
				except:
					print "error with overlay:",overlay
					print sys.exc_info()
		else:
			infoStr="n/a"
			rightsStr="n/a"
		self.serverInfos.set(infoStr)
		self.serverRights.set(rightsStr)
	
# -- Main -------------------------
def main(sargs):
	print "-- %s %s ----------------------" % (__application__,__version__)
	if len(bigmap.tile_servers)>0:
		# load config
		cfg=AppConfig(config.dbPath)
		cfg.load()
		# Start the GUI
		w=Tkinter.Tk()
		w.title("%s %s" % (__application__,__version__))
		i=main_gui(w,cfg)
		w.mainloop()
	else:
		print "error : no map servers defined"

#this calls the 'main' function when this script is executed
if __name__ == '__main__': 
	main(sys.argv[1:])
