#!/usr/bin/env python
# -*- coding: utf-8 -*-

# == projet description =====================================
__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"
__copyright__="Copyright 2016, Pierre-Alain Dorange"
__license__="BSD"
__version__="1.0a3"
__application__="Python Map eXplorer (pmx)"

# debug tags
_debug_sql=False

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
	Quadkey for Bing : http://www.web-maps.com/gisblog/?m=200903
	Longitude : https://en.wikipedia.org/wiki/Longitude
	Latitude : https://en.wikipedia.org/wiki/Latitude
	EPSG:3857 projection : https://en.wikipedia.org/wiki/Web_Mercator
	Nominatim : http://wiki.openstreetmap.org/wiki/Nominatim
	
-- History -----------------------------------------------------------------------------
	1.0a1 february 2016 : initial alpha
	1.0a2 march-june 2016 : 
		add SQLite3 dababase to store config (location, zoom and map)
		optimize overlay displaying
		optimize loading (adding a ram cache for bigmap.py)
	1.0a3 july-august 2016 :
		map resize according to window size, and adjust offscreen size
		add error tile
		add date widget
		add search via Nominatim service
"""
# == Standard Library =======================================
import os,sys,time
import threading	# multitask handling (threads)
import Queue		# queue handling
import sqlite3		# sql local database
import Tkinter		# Tkinter (TK/TCL for Python) : Simple standard GUI (no-OS dependant)
import tkFileDialog, tkMessageBox

# == Special Library (need seperate install) =================
from PIL import Image,ImageDraw,ImageTk		# Image manipulation library

# == Local library ===========================================
import config			# configobj 4 modified
import bigmap			# bigmap : handle downloading and assembling tiles
import pmx_map			# Map Widget for Tkinter
import bigmap_nominatim	# Nominatim interface (search location)

# == Code ====================================================

# trick to made utf-8 default encoder/decoder (python 2.x)
reload(sys)
sys.setdefaultencoding('utf8')

# -- GUI classes (using Tkinter) ---------------------

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
		self.params={	'VERSION':('str_value','2'),
						'MAP':('str_value',map),
						'OVERLAY':('str_value',overlay),
						'LONGITUDE':('real_value',(bigmap.config.default_loc0[0]+bigmap.config.default_loc1[0])/2),
						'LATITUDE':('real_value',(bigmap.config.default_loc0[1]+bigmap.config.default_loc1[1])/2),
						'ZOOM':('int_value',bigmap.config.default_zoom),
						'WIN_X':('int_value',pmx_map.default_win_x),
						'WIN_Y':('int_value',pmx_map.default_win_y),
						'QUERY':('str_value',bigmap.config.default_query)}
		self.results=[]
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
			sql_cmd="SELECT %s FROM params WHERE id = ?;" % field
			if _debug_sql:
				print sql_cmd,"=",id
			c.execute(sql_cmd,(id,))
			data=c.fetchone()
			if _debug_sql:
				print "\tresult:",data
			if data==None or len(data)==0:
				sql_cmd="INSERT INTO params (id,%s) VALUES (?,?);" % field
				if _debug_sql:
					print sql_cmd
				c.execute(sql_cmd,(id,str(value)))
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
			sql_cmd="UPDATE params SET %s=? WHERE id=?;" % field
			if _debug_sql:
				print sql_cmd
			c.execute(sql_cmd,(str(value),id))
			self.sql.commit()
			if close :
				c.close()
		except:
			print "param:",id,"do not exist"
			print sys.exc_info()
		
	def loadParams(self):
		""" load all parameters from local SQL database
		"""
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
		# check consistancy : mapname still valid
		mapname=self.get("MAP")
		for s in bigmap.tile_servers:
			if s.name==mapname:
				return
		# if not mapname valid, select the default one, or the first one
		mapname=""
		for s in bigmap.tile_servers:
			if s.name==bigmap.config.default_server:
				mapname=s.name
				break
		if len(mapname)==0:
			mapname=bigmap.tile_servers[0]
		self.set('MAP',mapname)
		
	def saveParams(self):
		""" Save all parameters to local SQL database
		"""
		cursor=self.sql.cursor()
		for k in self.params.keys():
			self.save1Param(k,cursor)
		cursor.close()
		
	def loadResults(self):
		cursor=self.sql.cursor()
		# create table if not allready done
		sql_cmd="CREATE TABLE IF NOT EXISTS results (osm_id INTEGER,name TEXT,osm_type TEXT,type TEXT,place INTEGER,longitude REAL,latitude REAL);"
		if _debug_sql:
			print sql_cmd
		cursor.execute(sql_cmd)
		self.sql.commit()
		# load
		sql_cmd="SELECT osm_id,name,osm_type,type,place,longitude,latitude FROM results;"
		if _debug_sql:
			print sql_cmd
		cursor.execute(sql_cmd)
		self.results=[]
		for i in cursor.fetchall():
			r=bigmap_nominatim.osm_object()
			r.id=int(i[0])
			r.name=i[1]
			r.osm_type=i[2]
			r.type=i[3]
			r.placeid=int(i[4])
			r.location=bigmap.Coordinate(float(i[5]),float(i[6]))
			self.results.append(r)
		cursor.close()
		
	def saveResults(self):
		cursor=self.sql.cursor()
		sql_cmd="DELETE FROM results;"
		cursor.execute(sql_cmd)
		sql_cmd="INSERT INTO results(osm_id,name,osm_type,type,place,longitude,latitude) VALUES(?,?,?,?,?,?,?);"
		for r in self.results:
			cursor.execute(sql_cmd,(r.id,r.name,r.osm_type,r.type,r.place_id,r.location.lon,r.location.lat))
		self.sql.commit()
		cursor.close()
		
class main_gui(Tkinter.Frame):
	""" display the main window : map exploxer
		based on Tkinter Frame class
	"""
	def __init__(self,root,cfg=None):
		""" init main GUI for pmx app
			load default config, last user settings and prepare widgets
		"""
		Tkinter.Frame.__init__(self,root)
		
		self.config=cfg
		self.root=root
		self.clock=time.clock()
		# load error tiles
		self.loadingImg=Image.open(config.loadingImgPath)
		self.loadingImg.load()
		self.errorImage={}
		for e in config.urlError:
			self.errorImage[e]=Image.open(config.errorImgPath[e])
			self.errorImage[e].load()
		# get config window size (last used)
		if self.config:
			w=self.config.get('WIN_X')
			h=self.config.get('WIN_Y')
		else:
			w=default_win_x
			h=default_win_y
		# default map config (get last parameters)
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
		print "cache size (actual):",self.cache
		
		# create Tkinter variables
		self.serverInfos=Tkinter.StringVar()
		self.serverRights=Tkinter.StringVar()
		self.setServerText(self.currentMap,self.currentOverlay)
		self.statusInfos=Tkinter.StringVar()
		self.statusInfos.set(str(self.cache))
		self.zoomInfos=Tkinter.StringVar()
		self.setZoomText("")
		self.dateInfos=Tkinter.StringVar()
		self.setDateText("")
		
		# create Widgets
		self.map=pmx_map.TMapWidget(self,width=w,height=h,cache=self.cache)
		self.zoomTxt=Tkinter.Label(self,textvariable=self.zoomInfos,anchor=Tkinter.W,justify=Tkinter.CENTER,font=("Arial",10))
		self.bZIn=Tkinter.Button(self,text="+",command=self.doZoomIn)
		self.bZOut=Tkinter.Button(self,text="-",command=self.doZoomOut)
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
		self.dateTxt=Tkinter.Label(self,textvariable=self.dateInfos,anchor=Tkinter.W,justify=Tkinter.CENTER,font=("Arial",10))
		self.bDateAdd=Tkinter.Button(self,text="+",command=self.doDateAdd)
		self.bDateMin=Tkinter.Button(self,text="-",command=self.doDateMin)
		self.bExport=Tkinter.Button(self,text="Export",command=self.doExport)
		self.bSearch=Tkinter.Button(self,text="Search",command=self.doSearch)
		
		# link widgets with function and/or other widget (scrollers)
		self.mList.bind("<<ListboxSelect>>",self.on_map_select)
		self.mScroll.configure(command=self.mList.yview)
		self.oList.bind("<<ListboxSelect>>",self.on_overlay_select)
		self.oScroll.configure(command=self.oList.yview)
		
		# load data into List widgets
		self.loadList()
		
		# define the grid configuration (using gridmanager)
		self.grid(sticky=Tkinter.NSEW,padx=5,pady=5)
		top=self.winfo_toplevel()
		top.columnconfigure(0,weight=1)
		top.rowconfigure(0,weight=1)
		self.columnconfigure(1,weight=1)
		self.rowconfigure(2,weight=1)
		self.rowconfigure(4,weight=1)
		# Use the Grid manager to fit all the widgets in the window at there respected position
		self.zoomTxt.grid(row=0,column=0,padx=2,pady=2)
		self.bZIn.grid(row=1,column=0,sticky=Tkinter.NW,padx=2,pady=2)
		self.bZOut.grid(row=2,column=0,sticky=Tkinter.NW,padx=2,pady=2)
		self.statusTxt.grid(row=0,column=1,sticky=Tkinter.NW,padx=2,pady=2)
		self.map.grid(row=1,column=1,rowspan=4,columnspan=2,sticky=Tkinter.NSEW,padx=0,pady=0)
		self.mListLabel.grid(row=1,column=3,sticky=Tkinter.NW,padx=2,pady=2)
		self.mList.grid(row=2,column=3,sticky=Tkinter.N+Tkinter.S,padx=0,pady=2)
		self.mScroll.grid(row=2,column=4,sticky=Tkinter.N+Tkinter.S+Tkinter.W,padx=0,pady=2)
		self.oListLabel.grid(row=3,column=3,sticky=Tkinter.NW,padx=2,pady=2)
		self.oList.grid(row=4,column=3,sticky=Tkinter.N+Tkinter.S,padx=0,pady=2)
		self.oScroll.grid(row=4,column=4,sticky=Tkinter.N+Tkinter.S+Tkinter.W,padx=0,pady=2)
		self.infoLabel.grid(row=5,column=1,sticky=Tkinter.NW,padx=2,pady=2)
		self.infoTxt.grid(row=6,column=1,sticky=Tkinter.NW,padx=2,pady=2)
		self.rightsLabel.grid(row=5,column=2,sticky=Tkinter.NW,padx=2,pady=2)
		self.rightsTxt.grid(row=6,column=2,sticky=Tkinter.NW,padx=2,pady=2)
		self.dateTxt.grid(row=0,column=3,padx=2,pady=2)
		self.bDateAdd.grid(row=0,column=4,sticky=Tkinter.NW,padx=2,pady=2)
		self.bDateMin.grid(row=0,column=5,sticky=Tkinter.NW,padx=2,pady=2)
		self.bExport.grid(row=5,column=3,padx=2,pady=2)
		self.bSearch.grid(row=6,column=3,padx=2,pady=2)
		# apply default config
		self.map.setMapServer(self.currentMap)
		self.map.setOverlayServer(self.currentOverlay)
		self.map.setLocation(dl,dz)
		self.map.setDate(time.strftime("%Y-%m-%d",time.localtime(time.time()-config.default_day_offset)))
		self.map.setShift(0)
		
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
			if s.handleDate:
				title=title+" [d]"
			if s.handleTimeShift:
				title=title+" [t]"
			if s.type=="overlay":
				self.oList.insert(Tkinter.END,title)
				self.overlays.append(s)
				if self.currentOverlay:
					if s.name==self.currentOverlay.name:
						oIndex=len(self.overlays)-1
						if pmx_map._debug_gui:
							print "default overlay:",oIndex,s.name
			else:
				self.mList.insert(Tkinter.END,title)
				self.maps.append(s)
				if self.currentMap:
					if s.name==self.currentMap.name:
						mIndex=len(self.maps)-1
						if pmx_map._debug_gui:
							print "default map:",mIndex,s.name
		self.mList.selection_set(mIndex)
		self.mList.see(mIndex)
		self.oList.selection_set(oIndex)
		self.oList.see(oIndex)
	
	def on_map_select(self,event):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			if pmx_map._debug_gui: print "select:",id
			self.currentMap=self.maps[id]
		else:
			id=-1
			if pmx_map._debug_gui: print "noselect:"
			self.currentMap=None
		if pmx_map._debug_gui: 			print "\tmap:",self.currentMap
		self.map.setMapServer(self.currentMap)
		self.setServerText(self.currentMap,self.currentOverlay)
	
	def on_overlay_select(self,event):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			if pmx_map._debug_gui: print "select:",id
			self.currentOverlay=self.overlays[id]
		else:
			id=-1
			if pmx_map._debug_gui: print "noselect:"
			self.self.currentOverlay=None
		if pmx_map._debug_gui: print "\tmap:",self.currentOverlay
		self.map.setOverlayServer(self.currentOverlay)
		self.setServerText(self.currentMap,self.currentOverlay)
	
	def doZoomIn(self):
		self.map.setZoom(self.map.zoom+1)
	
	def doZoomOut(self):
		self.map.setZoom(self.map.zoom-1)
		
	def setZoomText(self,txt):
		self.zoomInfos.set(txt)
	
	def doDateAdd(self,step=1):
		if self.map.handleDate:
			date=self.map.getDate()
			t=time.strptime(date,"%Y-%m-%d")
			t=time.mktime(t)+24.0*3600.0*step
			t0=time.mktime(time.localtime(time.time()-config.default_day_offset))
			if t<=t0:
				date=time.strftime("%Y-%m-%d",time.localtime(t))
				self.map.setDate(date)
		if self.map.handleTimeShift:
			shift=self.map.getShift()
			s=None
			if self.map.mapServer.handleTimeShift:
				s=self.map.mapServer.timeshift_string
			if self.map.overlayServer.handleTimeShift:
				s=self.map.overlayServer.timeshift_string
			if s==None:
				print "error: no map ahndling timeshift"
			else:
				shift=shift+step
				if shift>=len(s):
					shift=0
				self.map.setShift(shift)

	def doDateMin(self,step=1):
		if self.map.handleDate:
			date=self.map.getDate()
			t=time.strptime(date,"%Y-%m-%d")
			t=time.mktime(t)-24.0*3600.0*step
			date=time.strftime("%Y-%m-%d",time.localtime(t))
			self.map.setDate(date)
		if self.map.handleTimeShift:
			shift=self.map.getShift()
			s=None
			if self.map.mapServer.handleTimeShift:
				s=self.map.mapServer.timeshift_string
			if self.map.overlayServer.handleTimeShift:
				s=self.map.overlayServer.timeshift_string
			if s==None:
				print "error: no map ahndling timeshift"
			else:
				shift=shift-step
				if shift<0:
					shift=len(s)-1
				self.map.setShift(shift)
				
	def doExport(self):
		d=ExportDialog(self.root,self.map,title="Export current Map")
	
	def doSearch(self):
		d=SearchDialog(self.root,self.map,title="Search",query=self.config.get('QUERY'),results=self.config.results)
		if d.location:
			if d.zoom>0:
				self.map.setLocation(d.location,d.zoom)
			else:
				self.map.setLocation(d.location)
		# store query and results into params
		self.config.set('QUERY',d.query)
		self.config.results=d.results
		self.config.saveResults()

	def setDateText(self,txt=None):
		if txt==None:
			if self.map==None:
				txt="no server"
			else:
				if self.map.handleDate:
					date=self.map.getDate()
					txt="date:%s" % date
				if self.map.handleTimeShift:
					shift=self.map.getShift()
					str="-"
					if shift<len(self.map.mapServer.timeshift_string):
						str=self.map.mapServer.timeshift_string[shift]
					if self.map.overlayServer:
						if shift<len(self.map.overlayServer.timeshift_string):
							str=self.map.overlayServer.timeshift_string[shift]
					txt="timeshift:%s" % str
		self.dateInfos.set(txt)
	
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
		
class ExportDialog(Tkinter.Toplevel):
	""" Handle dialog window to export current map view to a file
	"""
	def __init__(self,parent,map,title=None):
		Tkinter.Toplevel.__init__(self,parent)
		self.transient(parent)
		if title:
			self.title(title)
		self.map=map
		self.zoommod=0
		self.filename=os.path.join(config.prgdir,"export.png")
		self.filevar=Tkinter.StringVar()
		self.filevar.set(self.filename)
		self.parent=parent
		self.result=None
		body=Tkinter.Frame(self)
		self.initial_focus=self.body(body)
		body.pack(padx=5,pady=5)
		self.buttonbox()
		self.grab_set()
		if not self.initial_focus:
			self.initial_focus=self
		self.protocol("WM_DELETE_WINDOW",self.cancel)
		self.geometry("+%d+%d" % (parent.winfo_rootx()+50,parent.winfo_rooty()+50))
		self.initial_focus.focus_set()
		self.wait_window(self)
		
	def body(self,master):
		pass	# override
		
	def buttonbox(self):
		# prepare options and data
		self.zoomVar=Tkinter.IntVar()
		self.zoomVar.set(self.zoommod)
		licence="map:%s by %s\nmap: %s\ntile: %s" % (self.map.mapServer.name,self.map.mapServer.provider,self.map.mapServer.tile_copyright,self.map.mapServer.data_copyright)
		if self.map.overlayServer:
			licence=licence+"\n\noverlay:%s by %s\nmap: %s\ntile: %s" % (self.map.overlayServer.name,self.map.overlayServer.provider,self.map.overlayServer.tile_copyright,self.map.overlayServer.data_copyright)
		# buld dialog GUI
		l=Tkinter.Label(self,text="Image size")
		l.pack(anchor=Tkinter.W)
		(min_zoom,max_zoom)=self.map.mapServer.getZoom()
		(sx,sy)=self.map.getOffscreenSize()
		mode=[]
		for (s,z) in [("Current",0),("High",1),("Very high",2)]:
			if max_zoom>=self.map.zoom+z:
				mode.append(("%s resolution (%d x %d pixels, z=%d)" % (s,sx*(z+1),sy*(z+1),self.map.zoom+z),z))
		for (txt,v) in mode:
			b=Tkinter.Radiobutton(self,text=txt,variable=self.zoomVar,value=v,command=self.setzoom)
			b.pack(anchor=Tkinter.W)
		l=Tkinter.Label(self,textvariable=self.filevar,font=("Arial",10))
		l.pack()
		fb=Tkinter.Button(self,text="Select image's name",command=self.choosefile)
		fb.pack()
		l=Tkinter.Label(self,text="WARNING : Respect licences and usage",font=("Arial",12,'bold'))
		l.pack()
		m=Tkinter.Message(self,text=licence,font=("Arial",10),width=350)
		m.pack()
		b=Tkinter.Button(self,text="OK",command=self.ok)
		b.pack(side=Tkinter.RIGHT,pady=10,padx=5)
		b=Tkinter.Button(self,text="Cancel",command=self.cancel)
		b.pack(side=Tkinter.RIGHT,pady=10,padx=5)
		# bind action buttons
		self.bind("<Return>",self.ok)
		self.bind("<Escape>",self.cancel)
		
	def setzoom(self):
		self.zoommod=self.zoomVar.get()
		
	def choosefile(self):
		default=os.path.basename(self.filename)
		self.filename=tkFileDialog.asksaveasfilename(initialfile=default,defaultextension='.png',title="Save actual map")
		self.filevar.set(self.filename)
		
	def ok(self,event=None):
		self.map.export(self.filename,self.zoommod)
		if not self.validate():
			self.initial_focus.focus_set()
			return
		self.withdraw()
		self.update_idletasks()
		self.apply()
		self.cancel()
		
	def cancel(self,event=None):
		self.filename=None
		self.parent.focus_set()
		self.destroy()
		
	def validate(self):
		return 1	# override
		
	def apply(self):
		pass	# override
		
		
class SearchDialog(Tkinter.Toplevel):
	""" Handle dialog window to search geographic location
	"""
	def __init__(self,parent,map,title=None,query="",results=[]):
		Tkinter.Toplevel.__init__(self,parent)
		self.transient(parent)
		if title:
			self.title(title)
		self.map=map
		self.query=query
		self.parent=parent
		self.results=results
		self.location=None
		self.zoom=0
		body=Tkinter.Frame(self)
		self.initial_focus=self.body(body)
		body.pack(padx=5,pady=5)
		self.buttonbox()
		self.grab_set()
		if not self.initial_focus:
			self.initial_focus=self
		self.protocol("WM_DELETE_WINDOW",self.cancel)
		self.geometry("+%d+%d" % (parent.winfo_rootx()+50,parent.winfo_rooty()+50))
		self.initial_focus.focus_set()
		self.wait_window(self)
		
	def body(self,master):
		pass	# override
		
	def buttonbox(self):
		# prepare options and data
		m=Tkinter.Message(self,text="Search location using Nominatim service",font=("Arial",12,"bold"),width=350)
		m.pack()
		r=Tkinter.Frame(self)
		l=Tkinter.Label(r,text="Query:")
		self.q=Tkinter.Entry(r,width=50)
		b=Tkinter.Button(r,text="Search",command=self.search)
		l.grid(row=0,column=0)
		self.q.grid(row=0,column=1)
		b.grid(row=0,column=2)
		r.pack()
		r=Tkinter.Frame(self)
		self.rListLabel=Tkinter.Label(r,text="Result(s)",anchor=Tkinter.W,font=("Arial",12,'bold'))
		self.rScroll=Tkinter.Scrollbar(r,orient=Tkinter.VERTICAL)
		self.rList=Tkinter.Listbox(r,width=80,height=12,relief=Tkinter.RIDGE,yscrollcommand=self.rScroll.set,font=("Arial",11))
		self.rListLabel.grid(row=0,column=0,sticky=Tkinter.NW)
		self.rList.grid(row=1,column=0,sticky=Tkinter.N+Tkinter.S)
		self.rScroll.grid(row=1,column=1,sticky=Tkinter.N+Tkinter.S+Tkinter.W)
		r.pack()
		self.bOk=Tkinter.Button(self,text="OK",command=self.ok,state=Tkinter.DISABLED)
		self.bOk.pack(side=Tkinter.RIGHT,pady=10,padx=5)
		b=Tkinter.Button(self,text="Cancel",command=self.cancel)
		b.pack(side=Tkinter.RIGHT,pady=10,padx=5)
		
		# bind action buttons
		self.rList.bind("<<ListboxSelect>>",self.on_result_select)
		self.rScroll.configure(command=self.rList.yview)
		self.bind("<Return>",self.ok)
		self.bind("<Escape>",self.cancel)
		#
		self.q.delete(0,Tkinter.END)
		self.q.insert(0,self.query)
		self.buildResultsList()
	
	def buildResultsList(self):
		self.rList.delete(0,Tkinter.END)
		for r in self.results:
			self.rList.insert(Tkinter.END,"(%s) %s" % (r.type,r.name))
	
	def search(self,event=None):
		self.query=self.q.get()
		q=bigmap_nominatim.query_url(self.query.split())
		q.download()
		self.results=q.xml_parse(self.map)
		self.buildResultsList()
		self.bOk.config(state=Tkinter.DISABLED)
	
	def on_result_select(self,event=None):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			self.location=self.results[id].location
			self.zoom=self.results[id].zoom
			self.bOk.config(state=Tkinter.NORMAL)
		else:
			self.location=None
			self.zoom=0
			self.bOk.config(state=Tkinter.DISABLED)
		
	def ok(self,event=None):
		if not self.validate():
			self.initial_focus.focus_set()
			return
		self.withdraw()
		self.update_idletasks()
		self.apply()
		self.cancel()
		
	def cancel(self,event=None):
		self.parent.focus_set()
		self.destroy()
		
	def validate(self):
		return 1	# override
		
	def apply(self):
		pass	# override
		
# -- Main -------------------------
def main(sargs):
	print "-- %s %s ----------------------" % (__application__,__version__)
	if len(bigmap.tile_servers)>0:
		# load config
		cfg=AppConfig(config.dbPath)
		cfg.loadParams()
		cfg.loadResults()
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
