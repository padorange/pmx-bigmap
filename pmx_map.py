#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" pmx_map.py
----------------------------------------------------------------------------------------
tkinter/map classes
See pmx.py for licence and usage details
"""

# debug tags
_debug_idle=False
_debug_gui=False
_debug_coord=False
_debug_chrono=True
_debug_offscreen=False
_debug_export=False

# == Standard Library =======================================
import os,sys,time
import threading,queue
import tkinter, tkinter.filedialog, tkinter.messagebox		# Tkinter (TK/TCL for Python) : Simple standard GUI (no-OS dependant)

# == Special Library (need seperate install) =================
from PIL import Image,ImageDraw,ImageTk		# Image manipulation library

# == Local library ==========================================
import config		# global configuration
import bigtilemap

# == Constants & Globals ==============================================
(default_win_x,default_win_y)=(800,600)
(default_win_pos_x,default_win_pos_y)=(20,20)
k_frame=20

# -- Map Classes ---------------------

class TMapWidget(tkinter.Canvas):
	""" the map canvas : handle displaying the map in a tkinter canvas
		used a tk's offscreen and rely on 2 bigtilemap objects for rendering map (base layout + overlay)
		also handle the task queue for loading tiles.
			mapOffscreen : the offscreen full image for map (larger than viewed, see bigtilemap.py)
			mapServer : map server used for base layout
			overlayOffscreen : the offscreen full image for overlay (larger than viewed, see bigyilemap.py)
			overlayServer : map server used for overlay
			tkOffscreen : the tk version of the offsceen image (mix map+overlay), to allow tkinter to handle draw in canvas
			work_queue : tiles to download
			result_queue : tiles downloaded and not displayed
			refresh (True) : update the complete map (zoom, server or canvas size changed)
			update (True) : update some tiles (scroll or loading)
	"""
	def __init__(self,window,width=default_win_x,height=default_win_y,cache=None):
		tkinter.Canvas.__init__(self,window,width=width,height=height,background="#fff0d4")
		self.parent=window
		self.item=None
		self.tkOffscreen=None
		self.loadingImg=window.loadingImg
		self.errorImg=window.errorImage
		self.mapOffscreen=bigtilemap.BigTileMap()			# main map (base)
		self.mapOffscreen.setErrorImage(self.errorImg)
		self.mapServer=None
		self.overlayOffscreen=bigtilemap.BigTileMap(overlay=True)		# overlmay ùmap (if any)
		self.overlayOffscreen.setErrorImage(self.errorImg)
		self.overlayServer=None
		self.location=None			# the center of the map (geographic coordinates)
		self.zoom=0					# zoom level
		self.date=None
		self.shift=0
		self.cache=cache	# the cache handler
		self.loading=False		# display the loading logo
		(self.xmin,self.ymin)=(0,0)		# size of the rendered map (offscreen) in pixels
		(self.xmax,self.ymax)=(0,0)
		(self.xdtile,self.ydtile)=(0,0)
		(self.offsetx,self.offsety)=(0,0)		# the offset of the rendered tile map and the displayed area
		# bind some tk GUI interface (catch events)
		self.bind("<ButtonPress-1>",self.onClicDown)
		self.bind("<ButtonRelease-1>",self.onClicUp)
		self.bind("<MouseWheel>",self.onMouseWheel)
		self.bind("<ButtonPress-4>",self.onMouseWheel)		# for Linux handle mouse wheel with button 4 & 5
		self.bind("<ButtonPress-5>",self.onMouseWheel)
		self.bind("<Double-Button-1>",self.onDoubleClic)
		self.bind("<Configure>",self.onResize)
		# create the task queue : 2 queue(s) : work (task to be done) / result (task results)
		self.work_queue=queue.Queue()
		self.result_queue=queue.Queue()
		self.refresh=True
		self.clock=0.0
		self.clock_nb=0
		self.clock_task=False
		self.fps_clock=0.0
		self.fps=0
		if _debug_offscreen:
			self.frame=0
		self.after(0,self.idle)		# force idle to finish initializing

	def onClicDown(self,event):
		""" Handle clic : first clic active drag motion """
		event.widget.bind ("<Motion>", self.onClicDrag)
		self.clicLoc=(event.x,event.y)
		self.originLoc=(event.x,event.y)
		if _debug_gui: 
			print("clic @",self.clicLoc)
		
	def onClicUp(self,event):
		""" handle clic release : stop drag motion """
		event.widget.unbind ("<Motion>")
		(mx,my)=(event.x-self.originLoc[0],event.y-self.originLoc[1])
		(mtx,mty)=(1.0*mx/self.mapServer.size_x,1.0*my/self.mapServer.size_y)
		(x,y)=self.location.convert2Tile(self.zoom)
		if _debug_gui: 
			print("release :", (mx,my),(mtx,mty))
		if _debug_coord:
			print("location (degrees) : ",self.location)
			print("tiles : ",(x,y),(int(x),int(y)))
			print("move (pixels) : ",(mx,my))
			print("move (tiles) : ",(mtx,mty))
		# adjust (new) location according to drag, and memorize
		self.location.convertFromTile((x-mtx,y-mty),self.zoom)
		self.parent.config.set('LONGITUDE',self.location.longitude)
		self.parent.config.set('LATITUDE',self.location.latitude)
		self.refresh=True
	
	def onClicDrag(self,event):
		""" handle drag (clic maintain and mouse moved) : 
			drag the map into the view (without loading) """
		(mx,my)=(event.x-self.clicLoc[0],event.y-self.clicLoc[1])
		(self.offsetx,self.offsety)=(self.offsetx-mx,self.offsety-my)
		self.updateMap()
		self.clicLoc=(event.x,event.y)
		if _debug_gui: 
			print("drag :",mx,my)
		
	def onMouseWheel(self,event):
		""" handle mouse wheel scroll : zoom in/out """
		if _debug_gui: 
			print("wheel",event.delta)
		if event.num==5 or event.delta<0:
			self.setZoom(self.zoom-1)
		else:
			self.setZoom(self.zoom+1)
	
	def onDoubleClic(self,event):
		""" handle double clic : move to this new location """
		(mx,my)=(event.x-self.winfo_width()/2,event.y-self.winfo_height()/2)
		(mtx,mty)=(1.0*mx/self.mapServer.size_x,1.0*my/self.mapServer.size_y)
		(x,y)=self.location.convert2Tile(self.zoom)
		if _debug_gui: 
			print("release :", (mx,my),(mtx,mty))
		if _debug_coord:
			print("location (degrees) : ",self.location)
			print("tiles : ",(x,y),(int(x),int(y)))
			print("move (pixels) : ",(mx,my))
			print("move (tiles) : ",(mtx,mty))
		loc=self.location
		loc.convertFromTile((x+mtx,y+mty),self.zoom)
		self.setLocation(loc)
		self.setZoom(self.zoom+1)
	
	def onResize(self,event):
		""" Handle resize of the canvas where the map is displayed :
			adjust sizes of the map and ask for a refresh of the map """
		# recompute the tiles box dimensions (bigger than window)
		self.xdtile=int((0.5*self.winfo_width()/self.mapServer.render_size_x)+1.0)
		self.ydtile=int((0.5*self.winfo_height()/self.mapServer.render_size_y)+1.0)
		self.refresh=True
		# memorize new default window size
		self.parent.config.set('WIN_X',self.winfo_width()-6)
		self.parent.config.set('WIN_Y',self.winfo_height()-6)
		if _debug_gui: 
			print("-- RESIZED ----------------")
			print("\twidget real size:",self.winfo_width(),self.winfo_height())
			print("\toffscreen size (tile):",self.xdtile,self.ydtile)
	
	def getWidgetSize(self):
		""" return the widget size """
		return (self.winfo_width(),self.winfo_height())
	
	def getOffscreenSize(self):
		""" return the offscreen size """
		return self.mapOffscreen.getSize()
		
	def setMapServer(self,map_server):
		""" define a new map server and store default (+update zoom if necessary) """
		if map_server:
			if self.mapServer!=map_server:
				self.mapServer=map_server
				mapname=self.mapServer.name
				self.parent.config.set('MAP',mapname)
				# update zoom/date/timeshift widget according to map and overlay
				self.handleTimeShift=False
				self.handleDate=False
				self.handleHour=False
				self.shift=0
				self.setZoom(self.zoom)
				if self.mapServer.handleDate:
					self.handleDate=True
				else:
					if self.overlayServer:
						if self.overlayServer.handleDate:
							self.handleDate=True
				if self.mapServer.handleHour:
					self.handleHour=True
				else:
					if self.overlayServer:
						if self.overlayServer.handleHour:
							self.handleHour=True
				if self.mapServer.handleTimeShift:
					self.handleTimeShift=True
				else:
					if self.overlayServer:
						if self.overlayServer.handleTimeShift:
							self.handleTimeShift=True
				if self.handleTimeShift and _debug_gui: 
					print("Timeshift")
				# refresh GUI according to new server
				self.parent.setDateText()
				self.onResize(None)
				self.refresh=True
		
	def setOverlayServer(self,overlay_server):
		""" define a new overlay server for the map from its name and store default (+update zoom) """
		if self.overlayServer!=overlay_server:
			self.overlayServer=overlay_server
			# store new setting nto config
			if self.overlayServer:
				mapname=self.overlayServer.name
			else:
				mapname=""
			self.parent.config.set('OVERLAY',mapname)
			# update zoom/date and timeshift if required
			self.setZoom(self.zoom)
			if self.overlayServer and self.overlayServer.handleDate:
				self.handleDate=True
			else:
				if self.mapServer.handleDate:
					self.handleDate=True
				else:
					self.handleDate=False
			if self.overlayServer and self.overlayServer.handleHour:
				self.handleHour=True
			else:
				if self.mapServer.handleHour:
					self.handleHour=True
				else:
					self.handleHour=False
			if self.overlayServer and self.overlayServer.handleTimeShift:
				self.handleTimeShift=True
			else:
				if self.mapServer.handleTimeShift:
					self.handleTimeShift=True
				else:
					self.handleTimeShift=False
			self.shift=0
			if self.handleTimeShift and _debug_gui: 
				print("Timeshift (overlay)")
			# refresh GUI according to new overlay
			self.parent.setDateText()
			self.onResize(None)
			self.refresh=True
	
	def setLocation(self,location,zoom=None):
		""" define a new location (with optional zoom) for the map and store default 
		location is expressed in geographic coordinates (longitude, latitude)
		"""
		if zoom:
			self.setZoom(zoom)
		if self.location!=location:		# set new location (and update config)-
			self.location=location
			self.parent.config.set('LONGITUDE',self.location.longitude)
			self.parent.config.set('LATITUDE',self.location.latitude)
			self.refresh=True
		
	def setZoom(self,zoom):
		""" define a new zoom for the map and store default, check for zoom boundary """
		(zmmin,zmmax)=self.mapServer.getZoom()
		if self.overlayServer:
			(zomin,zomax)=self.overlayServer.getZoom()
			zmin=max(zmmin,zomin)
			zmax=min(zmmax,zomax)
		else:
			(zmin,zmax)=(zmmin,zmmax)
		if zoom<zmin:
			z=zmin
		elif zoom>zmax:
			z=zmax
		else:
			z=zoom
		print("zoom:",self.zoom,">",z)
		if z!=self.zoom:	# set new zoom and update config
			self.zoom=z
			self.parent.setZoomText("z=%d" % self.zoom)
			self.parent.config.set('ZOOM',self.zoom)
			self.refresh=True
	
	def setDate(self,date=None):
		""" setDate : define a date (for mapserver using date : handleDate) """
		if date!=self.date:
			self.date=date
			self.parent.setDateText()
			self.refresh=True
	
	def setShift(self,shift):
		""" setShift : define a timeshift (for mapserver using timeshift : handleTimeShift) """
		if shift!=self.shift:
			self.shift=shift
			self.mapServer.timeshift=shift
			if self.overlayServer:
				self.overlayServer.timeshift=shift
			self.parent.setDateText()
			self.refresh=True
	
	def getDate(self):
		""" return the data (string format) linked with the map (for map using date) or the current date of others"""
		if self.date:
			return self.date
		else:
			return time.localtime(time.time()-config.default_day_offset)
	
	def getShift(self):
		""" return time shift for map handling timeshift """
		if self.shift:
			return self.shift
		else:
			return 0

	def idle(self):
		""" Handle updates : called when idle by tk GUI (and after __init__) """
		status=" / work: %d, result: %d" % (self.work_queue.qsize(),self.result_queue.qsize())
		self.parent.setStatus(status)
		old_status=self.loading
		if self.refresh:	# refreah : redraw the offscreen and request a display update
			self.refreshOffscreen()
			force_update=True
			if _debug_idle: 
				print("refresh")
		else:
			force_update=False
		if not(self.result_queue.empty()) or not(self.work_queue.empty()):	# work queue empty : no more tiles to process
			self.loading=True
			if _debug_chrono:
				if self.clock_task:
					self.clock=time.perf_counter()-self.clock
					if self.clock>0.0:
						print("download tiles: %d / speed: %.2f tps" % (self.clock_nb,self.clock_nb/self.clock))
					self.clock_nb=0
					self.clock_task=False
					self.clock=0
					if self.fps_clock>0.0:
						print("fps: %.2f fps" % (self.fps/self.fps_clock))
					self.fps=0
					self.fps_clock=0.0
		else:
			self.loading=False
		if self.loading!=old_status:	# update loading status
			force_update=True
		if _debug_idle: 
			print("\twork:",self.work_queue.qsize(),"\tresult:",self.result_queue.qsize())
		if not(self.result_queue.empty()) or force_update:	# if loading or force update : update the map
			self.updateMap()
			if _debug_idle: 
				print("update")
		self.after(k_frame,self.idle)
		
	def refreshOffscreen(self):
		""" refresh the map : create offscren and launch tiles loading (asynchronous)
			the offscren contain a "map" and an "overlay" (optionnal)
			base map elements (tiles) are loaded in priority
		"""
		# calculate coordinates for offscreen location and size
		# geographioc coordinates to tiles coordinates (center)
		(x,y)=self.location.convert2Tile(self.zoom)
		# redefine the tiles box coordinates
		self.xmin=int(x)-self.xdtile
		self.ymin=int(y)-self.ydtile
		self.xmax=int(x)+self.xdtile
		self.ymax=int(y)+self.ydtile
		# update offscreen maps sizes
		self.mapOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
		self.overlayOffscreen.setSize((self.xmin,self.ymin),(self.xmax,self.ymax))
		# compute offset to match center of the map (location) with the center of the area displayed
		sz=self.getWidgetSize()
		#sz=(self.winfo_width(),self.winfo_height())
		self.offsetx=int(self.mapServer.render_size_x*(x-int(x)+self.xdtile))-sz[0]/2
		self.offsety=int(self.mapServer.render_size_y*(y-int(y)+self.ydtile))-sz[1]/2
		if _debug_coord:
			print("location (degrees) : ",self.location)
			print("tiles : ",(x,y),(int(x),int(y)))
			print("tilebox:", (self.xmin,self.ymin),(self.xmax,self.ymax))
			print("map windows size (pixels):",sz)
			print("map size (tiles):",self.xdtile,self.ydtile)
			print("offset (pixels) : ",(self.offsetx,self.offsety))
		if _debug_chrono:
			self.clock=time.perf_counter()
			self.clock_task=True
			s=(self.xmax-self.xmin+1)*(self.ymax-self.ymin+1)
			if self.overlayServer:
				s=s*2
			self.clock_nb=self.clock_nb+s
		# fill the task queue with tiles to retrieve
		for x in range(self.xmin,self.xmax+1):
			for y in range(self.ymin,self.ymax+1) :
				self.work_queue.put((x,y,self.zoom,self.mapServer,self.date,self.shift,self.cache))
		if self.overlayServer:
			for x in range(self.xmin,self.xmax+1):
				for y in range(self.ymin,self.ymax+1) :
					self.work_queue.put((x,y,self.zoom,self.overlayServer,self.date,self.shift,self.cache))
		# launch the task queue (to retrieve tiles)
		if (config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queues
			for i in range(config.k_nb_thread):
				task=bigtilemap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
				task.start()
		else:	# for synchronous : run a single task until queue is empty
			task=bigtilemap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
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
			print("%d errors, force map assembly" % error)
		# create the offscreen and assemble into it
		if _debug_chrono: 
			self.fps_clock=self.fps_clock-time.perf_counter()
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
				map_img.paste(self.loadingImg,(int(x),int(y)),mask=self.loadingImg)
			# create TK image and copy map+overlay into it
			self.tkOffscreen=ImageTk.PhotoImage(map_img)
			self.delete(self.item)
			self.item=self.create_image(-self.offsetx,-self.offsety,image=self.tkOffscreen,anchor=tkinter.NW)
		if _debug_chrono: 
			self.fps_clock=self.fps_clock+time.perf_counter()
			self.fps=self.fps+1
		return map_img
		
	def export(self,filename="test.png",zoommod=0):
		""" do the rendering processing without user intercation 
			in order to build a big image and export it to a PNG file
		"""
		z=self.zoom
		if _debug_export:
			print("zoom:",z,"zmod:",zoommod)
		s=1
		while zoommod>0:
			z=z+1
			s=s+1
			zoommod=zoommod-1
		if _debug_export:
			print("zoom:",z,"size:",s)
		mapExport=TMapSimple(self.parent,self.winfo_width()*s,self.winfo_height()*s,self.cache)
		mapExport.setMapServer(self.mapServer)
		mapExport.setOverlayServer(self.overlayServer)
		mapExport.setLocation(self.location,z)
		mapExport.setDate(self.getDate())
		mapExport.setShift(self.getShift())
		mapExport.mapOffscreen._debug_build=True
		if _debug_chrono:
			img=mapExport.work_queue.qsize()
			clk=t=time.perf_counter()
		mapExport.update()
		while not(mapExport.ready()):
			pass
		if _debug_chrono:
			clk=time.perf_counter()-clk
			if clk==0.0:
				print("no timing, %d image(s)" % img)
			else:
				print("%d image(s) in %.1f : %.2f fps" % (img,clk,1.0*img/clk))
		img=mapExport.render()
		img.save(filename)
		if _debug_export:
			print("export:",filename)

class TMapSimple():
	"""	TMapSimple
		a simpliest version of TMapWidget without widget part
		full offscreen for exporting a file
	"""
	def __init__(self,window,width=default_win_x,height=default_win_y,cache=None):
		self.parent=window
		self.mapOffscreen=bigtilemap.BigTileMap()
		self.overlayOffscreen=bigtilemap.BigTileMap(overlay=True)
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
		self.work_queue=queue.Queue()
		self.result_queue=queue.Queue()
		self._debug_queue=False
		
	def setMapServer(self,map_server):
		""" define a new map server and store default (+update zoom) """
		if self.mapServer!=map_server:
			self.mapServer=map_server
			self.setZoom(self.zoom)		# update zoom
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
		(self.offsetx,self.offsety)=(int(self.mapServer.size_x*(x-int(x)+self.xdtile))-self.width/2,int(self.mapServer.size_y*(y-int(y)+self.ydtile))-self.height/2)
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
		if self._debug_queue:
			print("%d tiles" % self.jobs)
			print("launching : work: %d, result: %d" % (self.work_queue.qsize(),self.result_queue.qsize()))
		# launch the task queue (to retrieve tiles)
		if (config.k_nb_thread>1):		# for asyncrhonous : launch process to handle the queues
			for i in range(config.k_nb_thread):
				task=bigtilemap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
				task.start()
		else:	# for synchronous : run a single task until queue is empty
			task=bigtilemap.LoadImagesFromURL(self.work_queue,self.result_queue,self.errorImg)
			task.run()
	
	def ready(self):
		while not(self.result_queue.empty()):
			self.jobs=self.jobs-1
			self.result_queue.get()
			self.result_queue.task_done()
			if self._debug_queue:
				print("job done : work: %d, result: %d / left: %d" % (self.work_queue.qsize(),self.result_queue.qsize(),self.jobs))
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
	
