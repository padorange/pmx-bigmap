#!/usr/bin/env python
# -*- coding: utf-8 -*-

# == projet description =====================================
__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"
__copyright__="Copyright 2016, Pierre-Alain Dorange"
__license__="BSD"
__version__="1.0b1"
__workingdir__="bigmap"
__application__="Python Map eXplorer (pmx)"

_debug_idle=False
_debug_gui=False
_debug_coord=False

"""
pmx.py (Python Map eXplorer)
----------------------------------------------------------------------------------------
A Map Explorer software based on TMS online services (slippymap)

pmx rely on bigmap.py library (included)

usage: python pmx.py

See ReadMe.txt for detailed instructions
See bigmap.py for detail on TMS downloads.	
	
-- Requirements ------------------------------------------------------------------------
	Python 2.5
	Tkinter (include with python) for cross-platform GUI
	PIL Library : <http://www.pythonware.com/products/pil/>
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
	1.0b1 initial beta (march 2016)
"""
# == Standard Library =======================================
import os,sys,time
import threading,Queue
import Tkinter, tkFileDialog, tkMessageBox	# Tkinter (TK/TCL for Python) : Simple standard GUI (no-OS dependant)

# == Special Library (need seperate install) =================
from PIL import Image,ImageDraw,ImageTk		# Image manipulation library

# == Local library ==========================================
import bigmap

# == handle directory =======================================
# create the data directory and set paths for internal data and user data
# the default directory is the source code direcory, user data are stored in user folder (subfolder "ndsreader")

# get file name, to define the program name and get its directory
prgname=os.path.basename(__file__).rsplit('.',1)[0]
prgdir=os.path.dirname(os.path.abspath(sys.argv[0]))

# set working directory to user home directory (to store user data)
wrkdir=os.path.join(os.path.expanduser("~"),__workingdir__)
if not os.path.exists(wrkdir):		# create dir if it does not exist
	os.makedirs(wrkdir)

# set OS default directory to source directory (for internal in/out files, make launch independant location for files))
os.chdir(prgdir)

# -- GUI classes (using Tkinter) ---------------------

class TMap(Tkinter.Canvas):
	""" the map canvas :
			refresh (True) : update the complete map (zoom or server change)
			update (True) : update some tiles (scroll)
			offscreen : the offscreen full image (larger than viewed)
			offscreentk : the tk version of the offsceen image, to allow tkinter to handle draw
	"""
	def __init__(self,window,server=None,location=None,zoom=0,date=None,cache=None):
		Tkinter.Canvas.__init__(self,window,width=800,height=600,relief=Tkinter.RIDGE,background="#e1d2ac")
		self.parent=window
		self.item=None
		self.offscreentk=None
		self.offscreen=None
		self.server=None
		self.zoom=0
		self.location=None
		(self.xmin,self.ymin)=(0,0)
		(self.xmax,self.ymax)=(0,0)
		(self.offsetx,self.offsety)=(0,0)
		self.cache=cache
		self.setServer(server)
		self.setLocation(location,zoom)
		self.date=date
		self.bind("<ButtonPress-1>",self.clicDown)
		self.bind("<ButtonRelease-1>",self.clicUp)
		
		# create the task queue : 2 queue(s) : work (task to be done) / result (task results)
		self.work_queue=Queue.Queue()
		self.result_queue=Queue.Queue()
		self.refresh=True
		
		self.after(0,self.idle)
		
	def clicDown(self,event):
		""" Handle clic : first clic active drag motion """
		event.widget.bind ("<Motion>", self.clicDrag)
		self.clicLoc=(event.x,event.y)
		self.originLoc=(event.x,event.y)
		if _debug_gui: print "clic @",self.clicLoc
		
	def clicUp(self,event):
		""" handle clic release : stop drag motion """
		event.widget.unbind ("<Motion>")
		loc=(event.x,event.y)
		mov=(loc[0]-self.originLoc[0],loc[1]-self.originLoc[1])
		mt=(1.0*mov[0]/self.server.tile_size,1.0*mov[1]/self.server.tile_size)
		(x,y)=self.location.convert2Tile(self.zoom)
		if _debug_gui: print "release :", mov,mt
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "move (pixels) : ",mov
			print "move (tiles) : ",mt
		self.location.convertFromTile((x-mt[0],y-mt[1]),self.zoom)
		self.refresh=True
				
	def clicDrag(self,event):
		""" handle mouse motion when clic : drag the map """
		loc=(event.x,event.y)
		mov=(loc[0]-self.clicLoc[0],loc[1]-self.clicLoc[1])
		(self.offsetx,self.offsety)=(self.offsetx-mov[0],self.offsety-mov[1])
		self.updateMap()
		self.clicLoc=(event.x,event.y)
		if _debug_gui: print "drag :",mov
		
	def setLocation(self,location,zoom=None):
		if zoom:
			self.setZoom(zoom)
		if self.location!=location:
			self.location=location
			self.refresh=True
		
	def setZoom(self,zoom):
		(zmin,zmax)=self.server.getZoom()
		if zoom<zmin:
			z=zmin
		if zoom>zmax:
			z=zmax
		else:
			z=zoom
		if z!=self.zoom:
			self.zoom=z
			self.parent.setZoomText("z=%d" % self.zoom)
			self.refresh=True
		
	def setServer(self,server):
		if self.server!=server:
			self.server=server
			self.refresh=True
			self.setZoom(self.zoom)
		
	def idle(self):
		if self.refresh:
			self.refreshOffscreen()
			force_update=True
			if _debug_idle: print "refresh"
		else:
			force_update=False
		if not(self.result_queue.empty()) or force_update:
			self.updateMap()
			if _debug_idle: print "update"
		if self.work_queue.empty():
			status=""
		else:
			status=" (loading)"
		self.parent.setStatus(status)
		if _debug_idle: print "dt: %.2f" % dt,"\twork:",self.work_queue.qsize(),"\tresult:",self.result_queue.qsize()
		self.after(100,self.idle)
		
	def refreshOffscreen(self):
		(x,y)=self.location.convert2Tile(self.zoom)
		(self.xmin,self.ymin)=(int(x)-2,int(y)-2)
		(self.xmax,self.ymax)=(int(x)+2,int(y)+2)
		sz=(self.winfo_reqwidth(),self.winfo_reqheight())
		(self.offsetx,self.offsety)=(int(self.server.tile_size*(x-int(x)+2))-sz[0]/2,int(self.server.tile_size*(y-int(y)+2))-sz[1]/2)
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "tilebox:", (self.xmin,self.ymin),(self.xmax,self.ymax)
			print "map size:",sz
			print "offset (pixels) : ",(self.offsetx,self.offsety)
		for x in range(self.xmin,self.xmax+1):
			for y in range(self.ymin,self.ymax+1) :
				self.work_queue.put((x,y,self.zoom,self.server,self.date,self.cache))
		# handle the task queue
		if (bigmap.config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queue
			for i in range(bigmap.config.k_nb_thread):
				task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue)
				task.start()
		else:	# for synchronous : run a single task until queue is empty
			task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue)
			task.run()
		self.refresh=False
		
	def updateMap(self):
		# assemble tiles with PIL
		error=0
		while not(self.result_queue.empty()):
			e=self.result_queue.get()
			error+=e
			self.result_queue.task_done()
		if error>0:
			print "%d errors, force map assembly" % error
		self.offscreen=bigmap.BigMap(self.server,self.zoom,self.date)
		self.offscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
		self.offscreen.build()
		self.offscreentk=ImageTk.PhotoImage(self.offscreen.getImg())
		self.delete(self.item)
		self.item=self.create_image(-self.offsetx,-self.offsety,image=self.offscreentk,anchor=Tkinter.NW)

class main_gui(Tkinter.Frame):
	""" display the main window : map exploxer
	"""
	def __init__(self,window,cfg=None):
		Tkinter.Frame.__init__(self,window,width=800,height=600)
		
		if cfg:
			self.sql=cfg.sql
		self.clock=time.clock()
		
		# default map config
		self.currentMap=None
		self.currentOverlay=None
		for s in bigmap.tile_servers:
			if s.name==bigmap.config.default_server:
				self.currentMap=s
				break
		upleft=bigmap.Coordinate(bigmap.config.default_loc0[0],bigmap.config.default_loc0[1])
		downright=bigmap.Coordinate(bigmap.config.default_loc1[0],bigmap.config.default_loc1[1])
		dl=(upleft+downright)/2
		dz=bigmap.config.default_zoom
		
		# create the cache handler
		self.cache=bigmap.Cache(bigmap.config.k_cache_folder,bigmap.config.k_cache_max_size,bigmap.config.k_cache_delay)
		self.cache.setactive(True)
		self.cache.clear()
		print "cache size:",self.cache
		
		# create Tkinter variables
		self.serverInfos=Tkinter.StringVar()
		self.serverRights=Tkinter.StringVar()
		self.setServerText(self.currentMap)
		self.statusInfos=Tkinter.StringVar()
		self.statusInfos.set(str(self.cache))
		self.zoomInfos=Tkinter.StringVar()
		self.setZoomText("")
		
		# create Widgets
		self.map=TMap(self,server=self.currentMap,location=dl,zoom=dz,cache=self.cache,date=None)
		self.zoomTxt=Tkinter.Label(self,textvariable=self.zoomInfos,anchor=Tkinter.W,justify=Tkinter.CENTER,font=("Arial",10))
		self.statusTxt=Tkinter.Label(self,textvariable=self.statusInfos,anchor=Tkinter.W,justify=Tkinter.LEFT,font=("Arial",10))
		self.infoLabel=Tkinter.Label(self,text="Informations",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.infoTxt=Tkinter.Message(self,textvariable=self.serverInfos,anchor=Tkinter.W,justify=Tkinter.LEFT,width=350,font=("Arial",10))
		self.rightsLabel=Tkinter.Label(self,text="Droits",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.rightsTxt=Tkinter.Message(self,textvariable=self.serverRights,anchor=Tkinter.W,justify=Tkinter.LEFT,width=350,font=("Arial",10))
		self.mListLabel=Tkinter.Label(self,text="Fond(s) de carte",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.mScroll=Tkinter.Scrollbar(self,orient=Tkinter.VERTICAL)
		self.mList=Tkinter.Listbox(self,width=25,height=20,relief=Tkinter.RIDGE,yscrollcommand=self.mScroll.set,font=("Arial",12))
		self.oListLabel=Tkinter.Label(self,text="Couche(s)",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.oScroll=Tkinter.Scrollbar(self,orient=Tkinter.VERTICAL)
		self.oList=Tkinter.Listbox(self,width=25,height=10,relief=Tkinter.RIDGE,yscrollcommand=self.oScroll.set,font=("Arial",12))
		self.bZIn=Tkinter.Button(self,text="+",command=self.doZoomIn)
		self.bZOut=Tkinter.Button(self,text="-",command=self.doZoomOut)
		
		# link widgets with function and/or other widget (scrollers)
		self.mList.bind("<<ListboxSelect>>",self.on_map_select)
		self.mScroll.configure(command=self.mList.yview)
		self.oList.bind("<<ListboxSelect>>",self.on_overlay_select)
		self.oScroll.configure(command=self.oList.yview)
		
		# load data into List widgets
		self.loadList()
		
		# Use the Grid manager to fit all the widgets in the window at the defined position
		self.grid(padx=5,pady=5)
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
		
	def loadList(self):
		self.overlays=[]
		self.maps=[]
		mIndex=-1
		for s in bigmap.tile_servers:
			if s.type=="overlay":
				self.oList.insert(Tkinter.END,s.name)
				self.overlays.append(s)
			else:
				self.mList.insert(Tkinter.END,s.name)
				self.maps.append(s)
				if s.name==self.currentMap.name:
					mIndex=len(self.maps)-1
					print "default map:",mIndex,s.name
		self.mList.selection_set(mIndex)
		self.mList.see(mIndex)
	
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
		self.map.setServer(self.currentMap)
		self.setServerText(self.currentMap)
		
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
		
	def setServerText(self,server=None):
		if not(server):
			server=self.currentMap
		if server:
			try:
				str="%s (zoom:%d-%d)" % (server.name,server.min_zoom,server.max_zoom)
				if len(server.provider)>0 :
					str=str+" by %s" % server.provider
				if len(server.familly)>0 :
					str=str+"\nfamilly : %s" % server.familly
				if len(server.description)>0 :
					str=str+"\n%s" % server.description
				self.serverInfos.set(str)
				str="Tile Licence: %s\nData Licence: %s" % (server.tile_copyright,server.data_copyright)
				self.serverRights.set(str)
			except:
				print "error with currentMap:",server
				print sys.exc_info()
		else:
			self.serverInfos.set("n/a")
			self.serverRights.set("n/a")
	
	def on_overlay_select(self,event):
		self.currentOverlay=1
	
# -- Main -------------------------
def main(sargs):
	print "-- %s %s ----------------------" % (__application__,__version__)
	""" Start the GUI """
	w=Tkinter.Tk()
	w.title("%s %s" % (__application__,__version__))
	cfg=None
	i=main_gui(w,cfg)
	w.mainloop()

#this calls the 'main' function when this script is executed
if __name__ == '__main__': 
	main(sys.argv[1:])
