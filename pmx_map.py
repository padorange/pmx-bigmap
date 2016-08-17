#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" pmx_map.py (Map class for pmx.py)
----------------------------------------------------------------------------------------
See pmx.py for licence and usage details
"""

# debug tags
_debug_idle=False
_debug_gui=False
_debug_coord=False
_debug_chrono=False
_debug_offscreen=False

# == Standard Library =======================================
import os,sys,time
import threading,Queue
import Tkinter, tkFileDialog, tkMessageBox	# Tkinter (TK/TCL for Python) : Simple standard GUI (no-OS dependant)

# == Special Library (need seperate install) =================
from PIL import Image,ImageDraw,ImageTk		# Image manipulation library

# == Local library ==========================================
import config	# configobj 4 modified
import bigmap

# == Constants & Globals ==============================================
(default_win_x,default_win_y)=(800,600)
k_frame=20

# -- Map Classes ---------------------

class TMapWidget(Tkinter.Canvas):
	""" the map canvas :
			refresh (True) : update the complete map (zoom, server or canvas size changed)
			update (True) : update some tiles (scroll or loading)
			mapOffscreen : the offscreen full image for map (larger than viewed, see bigmap.py)
			overlayOffscreen : the offscreen full image for overlay (larger than viewed, see bigmap.py)
			tkOffscreen : the tk version of the offsceen image (mix map+overlay), to allow tkinter to handle draw in canvas
	"""
	def __init__(self,window,width=default_win_x,height=default_win_y,cache=None):
		Tkinter.Canvas.__init__(self,window,width=width,height=height,background="#fff0d4")
		self.parent=window
		self.item=None
		self.tkOffscreen=None
		self.mapOffscreen=bigmap.BigMap()
		self.overlayOffscreen=bigmap.BigMap(overlay=True)
		self.loadingImg=window.loadingImg
		self.errorImg=window.errorImage
		self.mapOffscreen.setErrorImage(self.errorImg)
		self.overlayOffscreen.setErrorImage(self.errorImg)
		self.mapServer=None
		self.overlayServer=None
		self.zoom=0
		self.location=None
		(self.xmin,self.ymin)=(0,0)
		(self.xmax,self.ymax)=(0,0)
		(self.offsetx,self.offsety)=(0,0)
		self.date=None
		self.shift=0
		self.cache=cache
		self.loading=False
		self.bind("<ButtonPress-1>",self.onClicDown)
		self.bind("<ButtonRelease-1>",self.onClicUp)
		self.bind("<MouseWheel>",self.onMouseWheel)
		self.bind("<Double-Button-1>",self.onDoubleClic)
		self.bind("<Configure>",self.onResize)
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
		if _debug_gui: print "drag :",mx,my
		
	def onMouseWheel(self,event):
		""" handle mouse wheel scroll : zoom in/out """
		if event.delta<0:
			self.setZoom(self.zoom-1)
		else:
			self.setZoom(self.zoom+1)
	
	def onDoubleClic(self,event):
		""" handle double clic : move to location """
		(mx,my)=(event.x-self.winfo_width()/2,event.y-self.winfo_height()/2)
		(mtx,mty)=(1.0*mx/self.mapServer.tile_size,1.0*my/self.mapServer.tile_size)
		(x,y)=self.location.convert2Tile(self.zoom)
		if _debug_gui: print "release :", (mx,my),(mtx,mty)
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "move (pixels) : ",(mx,my)
			print "move (tiles) : ",(mtx,mty)
		loc=self.location
		loc.convertFromTile((x+mtx,y+mty),self.zoom)
		self.setLocation(loc)
	
	def onResize(self,event):
		""" Handle resize of the canvas where the map is displayed :
			adjust size of the map and ask for a refresh of the map """
		self.xdtile=int((0.5*self.winfo_width()/self.mapServer.size_x)+0.5)
		self.ydtile=int((0.5*self.winfo_height()/self.mapServer.size_y)+0.5)
		self.refresh=True
		self.parent.config.set('WIN_X',self.winfo_width()-6)
		self.parent.config.set('WIN_Y',self.winfo_height()-6)
		if _debug_gui: 
			print "-- RESIZED ----------------"
			print "\twidget real size:",self.winfo_width(),self.winfo_height()
			print "\toffscreen size (tile):",self.xdtile,self.ydtile
	
	def getWidgetSize(self):
		return (self.winfo_width(),self.winfo_height())
	
	def getOffscreenSize(self):
		return self.mapOffscreen.getSize()
		
	def setMapServer(self,map_server):
		""" define a new map server and store default (+update zoom) """
		if self.mapServer!=map_server:
			self.mapServer=map_server
			self.setZoom(self.zoom)		# update zoom
			if self.mapServer:	# store current map into config
				mapname=self.mapServer.name
			else:
				mapname=""
			self.parent.config.set('MAP',mapname)
			# update date/timeshift widget according to map and overlay
			if self.mapServer.handleDate:
				self.handleDate=True
			else:
				if self.overlayServer:
					if self.overlayServer.handleDate:
						self.handleDate=True
				else:
					self.handleDate=False
			if self.mapServer.handleTimeShift:
				self.handleTimeShift=True
			else:
				if self.overlayServer:
					if self.overlayServer.handleTimeShift:
						self.handleTimeShift=True
				else:
					self.handleTimeShift=False
			self.shift=0
			if self.handleTimeShift: print "Timeshift"
			# refresh GUI
			self.parent.setDateText()
			self.onResize(None)
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
			if self.overlayServer and self.overlayServer.handleDate:
				self.handleDate=True
			else:
				if self.mapServer.handleDate:
					self.handleDate=True
				else:
					self.handleDate=False
			if self.overlayServer and self.overlayServer.handleTimeShift:
				self.handleTimeShift=True
			else:
				if self.mapServer.handleTimeShift:
					self.handleTimeShift=True
				else:
					self.handleTimeShift=False
			if self.handleTimeShift: print "Timeshift"
			# refresh GUI
			self.shift=0
			self.parent.setDateText()
			self.onResize(None)
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
	
	def setDate(self,date):
		if date!=self.date:
			self.date=date
			self.parent.setDateText()
			self.refresh=True
	
	def setShift(self,shift):
		if shift!=self.shift:
			self.shift=shift
			self.mapServer.timeshift=shift
			if self.overlayServer:
				self.overlayServer.timeshift=shift
			self.parent.setDateText()
			self.refresh=True
	
	def getDate(self):
		if self.date:
			return self.date
		else:
			return time.strftime("%Y-%m-%d",time.localtime(time.time()-config.default_day_offset))
	
	def getShift(self):
		if self.shift:
			return self.shift
		else:
			return 0

	def idle(self):
		""" Handle updates : called when idle """
		status=" / work: %d, result: %d" % (self.work_queue.qsize(),self.result_queue.qsize())
		self.parent.setStatus(status)
		old_status=self.loading
		if self.refresh:	# refreah : redraw the offscreen and request a display update
			self.refreshOffscreen()
			force_update=True
			if _debug_idle: print "refresh"
		else:
			force_update=False
#		if self.work_queue.empty():	# work queue empty : no more tiles to process
		if not(self.result_queue.empty()) or not(self.work_queue.empty()):	# work queue empty : no more tiles to process
			self.loading=True
			if _debug_chrono:
				if self.clock_task:
					self.clock=time.clock()-self.clock
					if self.clock>0.0:
						print "download tiles: %d / speed: %.2f tps" % (self.clock_nb,self.clock_nb/self.clock)
					self.clock_nb=0
					self.clock_task=False
					self.clock=0
					if self.fps_clock>0.0:
						print "fps: %.2f fps" % (self.fps/self.fps_clock)
					self.fps=0
					self.fps_clock=0.0
		else:
			self.loading=False
		if self.loading!=old_status:	# update loading status
			force_update=True
		if _debug_idle: print "\twork:",self.work_queue.qsize(),"\tresult:",self.result_queue.qsize()
		if not(self.result_queue.empty()) or force_update:	# if loading or force update : update the map
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
		sz=(self.winfo_width(),self.winfo_height())
		(self.offsetx,self.offsety)=(int(self.mapServer.tile_size*(x-int(x)+self.xdtile))-sz[0]/2,int(self.mapServer.tile_size*(y-int(y)+self.ydtile))-sz[1]/2)
		if _debug_coord:
			print "location (degrees) : ",self.location
			print "tiles : ",(x,y),(int(x),int(y))
			print "tilebox:", (self.xmin,self.ymin),(self.xmax,self.ymax)
			print "map size:",sz
			print "offset (pixels) : ",(self.offsetx,self.offsety)
		if _debug_chrono:
			self.clock=time.clock()
			self.clock_task=True
			s=(self.xmax-self.xmin+1)*(self.ymax-self.ymin+1)
			if self.overlayServer:
				s=s*2
			self.clock_nb=self.clock_nb+s
		for x in range(self.xmin,self.xmax+1):
			for y in range(self.ymin,self.ymax+1) :
				self.work_queue.put((x,y,self.zoom,self.mapServer,self.date,self.shift,self.cache))
		if self.overlayServer:
			for x in range(self.xmin,self.xmax+1):
				for y in range(self.ymin,self.ymax+1) :
					self.work_queue.put((x,y,self.zoom,self.overlayServer,self.date,self.shift,self.cache))
		# launch the task queue (to retrieve tiles)
		if (bigmap.config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queues
			for i in range(bigmap.config.k_nb_thread):
				task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
				task.start()
		else:	# for synchronous : run a single task until queue is empty
			task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
			task.run()
		self.refresh=False
		
	def updateMap(self,indicator=True):
		""" assemble tiles images (as soon as they were ready) with PIL into a big offscreen image
		"""
		# handle just ended jobs
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
			if indicator and self.loading:
				(iw,ih)=self.loadingImg.size
				(x,y)=((self.winfo_width()-iw)/2+self.offsetx,(self.winfo_height()-ih)/2+self.offsety)
				map_img.paste(self.loadingImg,(x,y),mask=self.loadingImg)
			# create TK image and copy map+overlay into it
			self.tkOffscreen=ImageTk.PhotoImage(map_img)
			self.delete(self.item)
			self.item=self.create_image(-self.offsetx,-self.offsety,image=self.tkOffscreen,anchor=Tkinter.NW)
		if _debug_chrono: 
			self.fps_clock=self.fps_clock+time.clock()
			self.fps=self.fps+1
		return map_img
		
	def export(self,filename="test.png",zoommod=0):
		z=self.zoom
		print "zoom:",z,"zmod:",zoommod
		s=1
		while zoommod>0:
			z=z+1
			s=s+1
			zoommod=zoommod-1
		print "zoom:",z,"size:",s
		map=TMapSimple(self.parent,self.winfo_width()*s,self.winfo_height()*s,self.cache)
		map.setMapServer(self.mapServer)
		map.setOverlayServer(self.overlayServer)
		map.setLocation(self.location,z)
		map.setDate(self.getDate())
		map.setShift(self.getShift())
		map.update()
		while not(map.ready()):
			pass
		img=map.render()
		img.save(filename)
		print "export:",filename

class TMapSimple():
	def __init__(self,window,width=default_win_x,height=default_win_y,cache=None):
		self.parent=window
		self.mapOffscreen=bigmap.BigMap()
		self.overlayOffscreen=bigmap.BigMap(overlay=True)
		self.errorImg=window.errorImage
		self.mapOffscreen.setErrorImage(self.errorImg)
		self.overlayOffscreen.setErrorImage(self.errorImg)
		self.width=width
		self.height=height
		self.mapServer=None
		self.overlayServer=None
		self.zoom=0
		self.location=None
		(self.xmin,self.ymin)=(0,0)
		(self.xmax,self.ymax)=(0,0)
		(self.offsetx,self.offsety)=(0,0)
		self.date=None
		self.shift=0
		self.cache=cache
		self.loading=False
		# create the task queue : 2 queue(s) : work (task to be done) / result (task results)
		self.work_queue=Queue.Queue()
		self.result_queue=Queue.Queue()
		
	def setMapServer(self,map_server):
		""" define a new map server and store default (+update zoom) """
		if self.mapServer!=map_server:
			self.mapServer=map_server
			self.setZoom(self.zoom)		# update zoom
			if self.mapServer:	# store current map into config
				mapname=self.mapServer.name
			else:
				mapname=""
			self.parent.config.set('MAP',mapname)
			# update date/timeshift widget according to map and overlay
			if self.mapServer.handleDate:
				self.handleDate=True
			else:
				if self.overlayServer:
					if self.overlayServer.handleDate:
						self.handleDate=True
				else:
					self.handleDate=False
			if self.mapServer.handleTimeShift:
				self.handleTimeShift=True
			else:
				if self.overlayServer:
					if self.overlayServer.handleTimeShift:
						self.handleTimeShift=True
				else:
					self.handleTimeShift=False
			self.shift=0
		
	def setOverlayServer(self,overlay_server):
		""" define a new overlay server for the map from its name and store default (+update zoom) """
		if self.overlayServer!=overlay_server:
			self.overlayServer=overlay_server
			self.setZoom(self.zoom)
			if self.overlayServer:
				mapname=self.overlayServer.name
			else:
				mapname=""
			if self.overlayServer and self.overlayServer.handleDate:
				self.handleDate=True
			else:
				if self.mapServer.handleDate:
					self.handleDate=True
				else:
					self.handleDate=False
			if self.overlayServer and self.overlayServer.handleTimeShift:
				self.handleTimeShift=True
			else:
				if self.mapServer.handleTimeShift:
					self.handleTimeShift=True
				else:
					self.handleTimeShift=False
			self.shift=0
	
	def setLocation(self,location,zoom=None):
		""" define a new location (with optional zoom) for the map and store default """
		if zoom:
			self.setZoom(zoom)
		if self.location!=location:
			self.location=location
		
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
	
	def setDate(self,date):
		if date!=self.date:
			self.date=date
	
	def setShift(self,shift):
		if shift!=self.shift:
			self.shift=shift
			self.mapServer.timeshift=shift
			if self.overlayServer:
				self.overlayServer.timeshift=shift
			
	def update(self):
		(x,y)=self.location.convert2Tile(self.zoom)
		(self.xdtile,self.ydtile)=(int((0.5*self.width/self.mapServer.size_x)+0.5),int((0.5*self.height/self.mapServer.size_y)+0.5))
		(self.xmin,self.ymin)=(int(x)-self.xdtile,int(y)-self.ydtile)
		(self.xmax,self.ymax)=(int(x)+self.xdtile,int(y)+self.ydtile)
		(self.offsetx,self.offsety)=(int(self.mapServer.tile_size*(x-int(x)+self.xdtile))-self.width/2,int(self.mapServer.tile_size*(y-int(y)+self.ydtile))-self.height/2)
		self.jobs=0
		for x in range(self.xmin,self.xmax+1):
			for y in range(self.ymin,self.ymax+1) :
				self.work_queue.put((x,y,self.zoom,self.mapServer,self.date,self.shift,self.cache))
				self.jobs=self.jobs+1
		if self.overlayServer:
			for x in range(self.xmin,self.xmax+1):
				for y in range(self.ymin,self.ymax+1) :
					self.work_queue.put((x,y,self.zoom,self.overlayServer,self.date,self.shift,self.cache))
					self.jobs=self.jobs+1
		print "%d tiles" % self.jobs
		print "launching : work: %d, result: %d" % (self.work_queue.qsize(),self.result_queue.qsize())
		# launch the task queue (to retrieve tiles)
		if (bigmap.config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queues
			for i in range(bigmap.config.k_nb_thread):
				task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
				task.start()
		else:	# for synchronous : run a single task until queue is empty
			task=bigmap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
			task.run()
	
	def ready(self):
		while not(self.result_queue.empty()):
			self.jobs=self.jobs-1
			self.result_queue.get()
			self.result_queue.task_done()
			print "job done : work: %d, result: %d / left: %d" % (self.work_queue.qsize(),self.result_queue.qsize(),self.jobs)
#		return self.work_queue.empty() and self.result_queue.empty()
		return self.jobs<1
			
	def render(self):
		map_img=None
		if self.mapServer:
			self.mapOffscreen.setServer(self.mapServer,self.zoom,self.date)
			self.mapOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
			self.mapOffscreen.build()
			map_img=self.mapOffscreen.getImg()
			if self.overlayServer:
				self.overlayOffscreen.setServer(self.overlayServer,self.zoom,self.date)
				self.overlayOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
				self.overlayOffscreen.build()
				layer=self.overlayOffscreen.getImg()
				map_img.paste(layer,mask=layer)
		return map_img
	