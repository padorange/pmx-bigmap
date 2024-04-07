#! /usr/bin/python3
# -*- coding: utf-8 -*-

# == projet description =====================================
__application__="Python Map eXplorer (pmx)"
__version__="1.0b1"
__copyright__="Copyright 2010-2024, Pierre-Alain Dorange"
__license__="BSD"
__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"

""" pmx.py (Python Map eXplorer)
----------------------------------------------------------------------------------------
A Map Explorer software based on TMS online services (slippymap)
pmx is a GUI for bigtilemap.py that can be used from Terminal.

usage: python pmx.py

See ReadMe.me for detailed instructions and some TMS configuration
See bigtilemap.py for detail on TMS downloads.	
	
-- Requirements ------------------------------------------------------------------------
	Python 3.9+
	Tkinter (included with most python distrib) for cross-platform GUI
	Pillow (ex. PIL) Library : <https://python-pillow.org/>
	
-- Licences ----------------------------------------------------------------------------
	New-BSD Licence, (c) 2010-2022 Pierre-Alain Dorange
	
-- References --------------------------------------------------------------------------
	See reference section in bigtilemap.py
	
-- History -----------------------------------------------------------------------------
	1.0a1 february 2016 : initial alpha
	1.0a2 march-june 2016 : 
		add SQLite3 dababase to store config (location, zoom and map)
		optimize overlay displaying
		optimize loading (adding a ram cache for bigtilemap.py)
	1.0a3 july-august 2016 :
		map resize according to window size, and adjust offscreen size
		add error tile (need more work)
		add date widget (for date compatible service)
	1.0a4 august 2016
		add search via Nominatim service with results storage and autozoom
	1.0a5 june 2019
		few adapation for Debian
	1.0a6 june 2021
		adding more TMS
		prepare for Python 3 compatibility
	1.0a7 november 2022
		go to python 3 (finaly)
		reduce dependency (remove ConfigObj goes to standard configparser)
		clean TMS servers list (remove obsolete, add new)
		review date-time handling for TMS with date or date-time
		GUI :	+/- buttons now are the same size
				doubleclic : now recenter AND zoom in
				handle mousewheel for linux
	To do :
		optimize download :
			respect 2 threads but per server (allow more for other servers)
			optimize url error (one stop the others ?)
			when server changed, stop the old-current threads
		better GUI :
			infos box change window size
			think of a new lists for browse through servers
		better handling for download error (server, 403. 404...)
		study replacing servers.ini with a MySQL databse and permit an offline update ?
"""
# == Standard Library =======================================
import os,sys,time
import math
import threading	# multitask handling (threads)
import sqlite3		# sql local database
if sys.version_info.major==2:	# python 2.x
	import ConfigParser as configparser		# INI file handler for Python 2.x
	import Queue as queue
	import urllib2
	urllib2.install_opener(urllib2.build_opener())		# just to disable a bug in MoxOS X 10.6 : force to load CoreFoundation in main thread
else:							# python 3.x
	import configparser						#  INI file handler for Python 3.x
	import queue
	import urllib.request,urllib.error,urllib.parse
import tkinter, tkinter.filedialog, tkinter.messagebox		# Tkinter (TK/TCL for Python) : Simple standard GUI (no-OS dependant)

# == Special Library (need seperate install) =================
from PIL import Image,ImageDraw,ImageTk		# Image manipulation library

# == Local library ===========================================
import bigtilemap		# bigtilemap : handle downloading and assembling tiles
import pmx_map			# Map Widget for Tkinter
import bigtilemap_nominatim	# Nominatim interface (search location)
import config

# debug tags
_debug_sql=False
_chrono_map=True

# == Code ====================================================

# trick to made utf-8 default encoder/decoder (python 2.x)
if sys.version_info.major==2:
	reload(sys)
	sys.setdefaultencoding('utf8')

# -- GUI classes (using Tkinter) ---------------------

class AppConfig():
	""" Handle default config (saved in SQLite database)
		- save/load config into a SQLite database
		- accessor for the App to the config
	"""
	def __init__(self,dbPath):
		if _debug_sql: print("pmx database:",dbPath)
		map_name=""
		for s in bigtilemap.tile_servers:
			if s.name==bigtilemap.config.default_server:
				map_name=s.name
				break
		overlay=""
		self.params={	'VERSION':('str_value','3'),
						'MAP':('str_value',map_name),
						'OVERLAY':('str_value',overlay),
						'LONGITUDE':('real_value',(bigtilemap.config.default_loc0[0]+bigtilemap.config.default_loc1[0])/2),
						'LATITUDE':('real_value',(bigtilemap.config.default_loc0[1]+bigtilemap.config.default_loc1[1])/2),
						'ZOOM':('int_value',bigtilemap.config.default_zoom),
						'WIN_POS_X':('int_value',pmx_map.default_win_pos_x),
						'WIN_POS_Y':('int_value',pmx_map.default_win_pos_y),
						'WIN_X':('int_value',pmx_map.default_win_x),
						'WIN_Y':('int_value',pmx_map.default_win_y),
						'QUERY':('str_value',bigtilemap.config.default_query)}
		self.results=[]
		self.sql=sqlite3.connect(dbPath)
	
	def get(self,id):
		try:
			(field,value)=self.params[id]
		except:
			print("param:",id,"do not exist")
			print(sys.exc_info())
			value=None
		return value
	
	def set(self,id,value):
		try:
			(field,old)=self.params[id]
			if (old!=value):
				self.params[id]=(field,value)
				self.save1Param(id,value)
		except:
			print("param:",id,"do not exist")
			print(sys.exc_info())
	
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
			if _debug_sql: print(sql_cmd,"=",id)
			c.execute(sql_cmd,(id,))
			data=c.fetchone()
			if _debug_sql: print("\tresult:",data)
			if data==None or len(data)==0:
				sql_cmd="INSERT INTO params (id,%s) VALUES (?,?);" % field
				if _debug_sql: print(sql_cmd)
				c.execute(sql_cmd,(id,str(value)))
				self.sql.commit()
			else:
				value=data[0]
				self.params[id]=(field,value)
		except:
			value=None
			print("param:",id,"do not exist")
			print(sys.exc_info())
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
			if _debug_sql: print(sql_cmd)
			c.execute(sql_cmd,(str(value),id))
			self.sql.commit()
			if close :
				c.close()
		except:
			print("param:",id,"do not exist")
			print(sys.exc_info())
		
	def loadParams(self):
		""" load all parameters from local SQL database
		"""
		cursor=self.sql.cursor()
		# create table if not allready done
		sql_cmd="CREATE TABLE IF NOT EXISTS params (id TEXT PRIMARY KEY,str_value TEXT,int_value INTEGER,real_value REAL);"
		if _debug_sql: print(sql_cmd)
		cursor.execute(sql_cmd)
		self.sql.commit()
		# load params
		for k in self.params.keys():
			self.load1Param(k,cursor)
		cursor.close()
		# check consistancy : mapname still valid
		mapname=self.get("MAP")
		for s in bigtilemap.tile_servers:
			if s.name==mapname:
				return
		# if not mapname valid, select the default one, or the first one
		mapname=""
		for s in bigtilemap.tile_servers:
			if s.name==bigtilemap.config.default_server:
				mapname=s.name
				break
		if len(mapname)==0:
			mapname=bigtilemap.tile_servers[0]
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
		sql_cmd="CREATE TABLE IF NOT EXISTS results (osm_id INTEGER,name TEXT,osm_type TEXT,type TEXT,place INTEGER,longitude REAL,latitude REAL,lon0 REAL,lon1 REAL,lat0 REAL,lat1 REAL);"
		if _debug_sql: print(sql_cmd)
		cursor.execute(sql_cmd)
		self.sql.commit()
		# load
		sql_cmd="SELECT osm_id,name,osm_type,type,place,longitude,latitude,lon0,lon1,lat0,lat1 FROM results;"
		if _debug_sql: print(sql_cmd)
		cursor.execute(sql_cmd)
		self.results=[]
		for i in cursor.fetchall():
			r=bigtilemap_nominatim.osm_object()
			r.id=int(i[0])
			r.name=i[1]
			r.osm_type=i[2]
			r.type=i[3]
			r.placeid=int(i[4])
			r.location=bigtilemap.Coordinate(float(i[5]),float(i[6]))
			leftup=bigtilemap.Coordinate(float(i[7]),float(i[9]))
			rightdown=bigtilemap.Coordinate(float(i[8]),float(i[10]))
			r.box=bigtilemap.BoundingBox(leftup,rightdown)
			self.results.append(r)
		cursor.close()
		
	def saveResults(self):
		cursor=self.sql.cursor()
		sql_cmd="DELETE FROM results;"
		cursor.execute(sql_cmd)
		sql_cmd="INSERT INTO results(osm_id,name,osm_type,type,place,longitude,latitude,lon0,lon1,lat0,lat1) VALUES(?,?,?,?,?,?,?,?,?,?,?);"
		for r in self.results:
			cursor.execute(sql_cmd,(r.id,r.name,r.osm_type,r.type,r.place_id,r.location.lon,r.location.lat,r.box.leftup.lon,r.box.rightdown.lon,r.box.leftup.lat,r.box.rightdown.lat))
		self.sql.commit()
		cursor.close()
		
class main_gui(tkinter.Frame):
	""" display the main window : map exploxer
		based on tkinter Frame class
	"""
	def __init__(self,root,cfg=None):
		""" init main GUI for pmx app
			load default config, last user settings and prepare widgets
		"""
		tkinter.Frame.__init__(self,root)
		
		self.config=cfg
		self.root=root
		self.clock=time.perf_counter()
		# load error tiles
		self.loadingImg=Image.open(config.loadingImgPath)
		self.loadingImg.load()
		self.errorImage={}		# load error images
		for e in config.urlError:
			self.errorImage[e]=Image.open(config.errorImgPath[e])
			self.errorImage[e].load()
		# get config window size (last used)
		if self.config:
			x=self.config.get('WIN_POS_X')
			y=self.config.get('WIN_POS_Y')
			w=self.config.get('WIN_X')
			h=self.config.get('WIN_Y')
		else:
			x=default_win_pos_x
			y=default_win_pos_y
			w=default_win_x
			h=default_win_y
		self.root.title("%s %s" % (__application__,__version__))
		# default map config (get last parameters)
		self.currentMap=None
		self.currentOverlay=None
		map=self.config.get('MAP')
		for s in bigtilemap.tile_servers:
			if s.name==map:
				self.currentMap=s
				break
		overlay=self.config.get('OVERLAY')
		for s in bigtilemap.tile_servers:
			if s.name==overlay:
				self.currentOverlay=s
				break
		lon=self.config.get('LONGITUDE')
		lat=self.config.get('LATITUDE')
		dl=bigtilemap.Coordinate(lon,lat)
		dz=self.config.get('ZOOM')
		
		# create the cache handler
		self.cache=bigtilemap.Cache(bigtilemap.config.cachePath,bigtilemap.config.k_cache_max_size,bigtilemap.config.k_cache_delay)
		self.cache.setactive(True)
		self.cache.clear()
		print("cache size (actual):",self.cache)
		
		# create Tkinter variables
		self.serverInfos=tkinter.StringVar()
		self.serverRights=tkinter.StringVar()
		self.setServerText(self.currentMap,self.currentOverlay)
		self.statusInfos=tkinter.StringVar()
		self.statusInfos.set(str(self.cache))
		self.zoomInfos=tkinter.StringVar()
		self.setZoomText("")
		self.dateInfos=tkinter.StringVar()
		self.setDateText("")
		
		# createTkinter Widgets
		self.map=pmx_map.TMapWidget(self,width=w,height=h,cache=self.cache)
		self.zoomTxt=tkinter.Label(self,textvariable=self.zoomInfos,anchor=tkinter.W,justify=tkinter.CENTER,font=("Arial",10))
		self.bZIn=tkinter.Button(self,text="+",width=1,command=self.doZoomIn)
		self.bZOut=tkinter.Button(self,text="-",width=1,command=self.doZoomOut)
		self.statusTxt=tkinter.Label(self,textvariable=self.statusInfos,anchor=tkinter.W,justify=tkinter.LEFT,font=("Arial",10))
		self.infoLabel=tkinter.Label(self,text="Informations",anchor=tkinter.W,font=("Arial",12,'bold'))
		self.infoTxt=tkinter.Message(self,textvariable=self.serverInfos,anchor=tkinter.W,justify=tkinter.LEFT,width=350,font=("Arial",10))
		self.rightsLabel=tkinter.Label(self,text="Legals",anchor=tkinter.W,font=("Arial",12,'bold'))
		self.rightsTxt=tkinter.Message(self,textvariable=self.serverRights,anchor=tkinter.W,justify=tkinter.LEFT,width=350,font=("Arial",10))
		self.mListLabel=tkinter.Label(self,text="Map",anchor=tkinter.W,font=("Arial",12,'bold'))
		self.mScroll=tkinter.Scrollbar(self,orient=tkinter.VERTICAL)
		self.mList=tkinter.Listbox(self,width=28,height=20,relief=tkinter.RIDGE,yscrollcommand=self.mScroll.set,font=("Arial",11),exportselection=0)
		self.oListLabel=tkinter.Label(self,text="Overlay",anchor=tkinter.W,font=("Arial",12,'bold'))
		self.oScroll=tkinter.Scrollbar(self,orient=tkinter.VERTICAL)
		self.oList=tkinter.Listbox(self,width=28,height=10,relief=tkinter.RIDGE,yscrollcommand=self.oScroll.set,font=("Arial",11),exportselection=0)
		self.dateTxt=tkinter.Label(self,textvariable=self.dateInfos,anchor=tkinter.W,justify=tkinter.CENTER,font=("Arial",10))
		self.bDateAdd=tkinter.Button(self,text="+",width=1,command=self.doDateAdd)
		self.bDateMin=tkinter.Button(self,text="-",width=1,command=self.doDateMin)
		self.bExport=tkinter.Button(self,text="Export",command=self.doExport)
		self.bSearch=tkinter.Button(self,text="Search",command=self.doSearch)
		
		# link widgets with function and/or other widget (scrollers)
		self.mList.bind("<<ListboxSelect>>",self.on_map_select)
		self.mScroll.configure(command=self.mList.yview)
		self.oList.bind("<<ListboxSelect>>",self.on_overlay_select)
		self.oScroll.configure(command=self.oList.yview)
		
		# load data into List widgets
		self.loadList()
		
		# define the grid configuration (using gridmanager)
		self.grid(sticky=tkinter.NSEW,padx=5,pady=5)
		top=self.winfo_toplevel()
		top.columnconfigure(0,weight=1)
		top.rowconfigure(0,weight=1)
		self.columnconfigure(1,weight=1)
		self.rowconfigure(2,weight=1)
		self.rowconfigure(4,weight=1)
		# Use the Grid manager to fit all the widgets in the window at there respected position
		self.zoomTxt.grid(row=0,column=0,padx=2,pady=2)
		self.bZIn.grid(row=1,column=0,sticky=tkinter.NW,padx=2,pady=2)
		self.bZOut.grid(row=2,column=0,sticky=tkinter.NW,padx=2,pady=2)
		self.statusTxt.grid(row=0,column=1,sticky=tkinter.NW,padx=2,pady=2)
		self.map.grid(row=1,column=1,rowspan=4,columnspan=2,sticky=tkinter.NSEW,padx=0,pady=0)
		self.mListLabel.grid(row=1,column=3,sticky=tkinter.NW,padx=2,pady=2)
		self.mList.grid(row=2,column=3,sticky=tkinter.N+tkinter.S,padx=0,pady=2)
		self.mScroll.grid(row=2,column=4,sticky=tkinter.N+tkinter.S+tkinter.W,padx=0,pady=2)
		self.oListLabel.grid(row=3,column=3,sticky=tkinter.NW,padx=2,pady=2)
		self.oList.grid(row=4,column=3,sticky=tkinter.N+tkinter.S,padx=0,pady=2)
		self.oScroll.grid(row=4,column=4,sticky=tkinter.N+tkinter.S+tkinter.W,padx=0,pady=2)
		self.infoLabel.grid(row=5,column=1,sticky=tkinter.NW,padx=2,pady=2)
		self.infoTxt.grid(row=6,column=1,sticky=tkinter.NW,padx=2,pady=2)
		self.rightsLabel.grid(row=5,column=2,sticky=tkinter.NW,padx=2,pady=2)
		self.rightsTxt.grid(row=6,column=2,sticky=tkinter.NW,padx=2,pady=2)
		self.dateTxt.grid(row=0,column=3,padx=2,pady=2)
		self.bDateAdd.grid(row=0,column=4,sticky=tkinter.NW,padx=2,pady=2)
		self.bDateMin.grid(row=0,column=5,sticky=tkinter.NW,padx=2,pady=2)
		self.bExport.grid(row=5,column=3,padx=2,pady=2)
		self.bSearch.grid(row=6,column=3,padx=2,pady=2)
		# apply default config
		self.map.setMapServer(self.currentMap)
		self.map.setOverlayServer(self.currentOverlay)
		self.map.setLocation(dl,dz)
		self.map.setDate(time.localtime(time.time()-config.default_day_offset))
		self.map.setShift(0)
		
	def quit(self):
		self.config.save()
		tkinter.Frame.quit(self)
		
	def loadList(self):
		self.oList.insert(tkinter.END,"None")
		self.overlays=[None]
		self.maps=[]
		mIndex=-1
		oIndex=-1
		for s in bigtilemap.tile_servers:
			title="%s (%d-%d)" % (s.name,s.min_zoom,s.max_zoom)
			if s.handleDate:
				title=title+" [d]"
			if s.handleHour:
				title=title+" [dt]"
			if s.handleTimeShift:
				title=title+" [t]"
			if s.type=="overlay":
				self.oList.insert(tkinter.END,title)
				self.overlays.append(s)
				if self.currentOverlay:
					if s.name==self.currentOverlay.name:
						oIndex=len(self.overlays)-1
						if pmx_map._debug_gui: print("default overlay:",oIndex,s.name)
			else:
				self.mList.insert(tkinter.END,title)
				self.maps.append(s)
				if self.currentMap:
					if s.name==self.currentMap.name:
						mIndex=len(self.maps)-1
						if pmx_map._debug_gui: print("default map:",mIndex,s.name)
		self.mList.selection_set(mIndex)
		self.mList.see(mIndex)
		self.oList.selection_set(oIndex)
		self.oList.see(oIndex)
	
	def on_map_select(self,event):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			if pmx_map._debug_gui: print("select:",id)
			self.currentMap=self.maps[id]
		else:
			id=-1
			if pmx_map._debug_gui: print("noselect:")
			self.currentMap=None
		if pmx_map._debug_gui: print("\tmap:",self.currentMap)
		self.map.setMapServer(self.currentMap)
		self.setServerText(self.currentMap,self.currentOverlay)
	
	def on_overlay_select(self,event):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			if pmx_map._debug_gui: print("select:",id)
			self.currentOverlay=self.overlays[id]
		else:
			id=-1
			if pmx_map._debug_gui: print("noselect:")
			self.currentOverlay=None
		if pmx_map._debug_gui: print("\tmap:",self.currentOverlay)
		self.map.setOverlayServer(self.currentOverlay)
		self.setServerText(self.currentMap,self.currentOverlay)
	
	def doZoomIn(self):
		self.map.setZoom(self.map.zoom+1)
	
	def doZoomOut(self):
		self.map.setZoom(self.map.zoom-1)
		
	def setZoomText(self,txt):
		self.zoomInfos.set(txt)
	
	def modDate(self,step):
		st=self.map.getDate()
		if st:
			t=time.mktime(st)
			if self.map.handleDate:
				t=t+step*(24.0*3600.0)
			if self.map.handleHour:
				t=t+step*3600.0
			t0=time.mktime(time.localtime(time.time()-config.default_day_offset))
			if t<=t0:
				st=time.localtime(t)
				self.map.setDate(st)
		if self.map.handleTimeShift:
			shift=self.map.getShift()
			s=None
			if self.map.mapServer.handleTimeShift:
				s=self.map.mapServer.timeshift_string
			if self.map.overlayServer.handleTimeShift:
				s=self.map.overlayServer.timeshift_string
			if s==None: print("error: no map ahndling timeshift")
			else:
				shift=shift+step
				if shift>=len(s):
					shift=0
				self.map.setShift(shift)
	
	def doDateAdd(self):
		self.modDate(1)

	def doDateMin(self):
		self.modDate(-1)
				
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
				st=self.map.getDate()
				if self.map.handleDate:
					txt="date:%s" % time.strftime('%Y-%m-%d',st)
				if self.map.handleHour:
					txt="time:%s" % time.strftime('%Y-%m-%d %H:%M',st)
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
		if time.perf_counter()>self.clock:
			self.cacheStrSize=str(self.cache)
			self.clock=time.perf_counter()+2.0
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
				print("error with currentMap:",server)
				print(sys.exc_info())
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
					print("error with overlay:",overlay)
					print(sys.exc_info())
		else:
			infoStr="n/a"
			rightsStr="n/a"
		self.serverInfos.set(infoStr)
		self.serverRights.set(rightsStr)
		
class ExportDialog(tkinter.Toplevel):
	""" Handle dialog window to export current map view to a file
	"""
	def __init__(self,parent,map,title=None):
		tkinter.Toplevel.__init__(self,parent)
		self.transient(parent)
		if title:
			self.title(title)
		self.map=map
		self.zoommod=0
		self.filename=os.path.join(config.prgdir,"export.png")
		self.filevar=tkinter.StringVar()
		self.filevar.set(self.filename)
		self.parent=parent
		self.result=None
		body=tkinter.Frame(self)
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
		self.zoomVar=tkinter.IntVar()
		self.zoomVar.set(self.zoommod)
		licence="map:%s by %s\nmap: %s\ntile: %s" % (self.map.mapServer.name,self.map.mapServer.provider,self.map.mapServer.tile_copyright,self.map.mapServer.data_copyright)
		if self.map.overlayServer:
			licence=licence+"\n\noverlay:%s by %s\nmap: %s\ntile: %s" % (self.map.overlayServer.name,self.map.overlayServer.provider,self.map.overlayServer.tile_copyright,self.map.overlayServer.data_copyright)
		# buld dialog GUI
		l=tkinter.Label(self,text="Image size")
		l.pack(anchor=tkinter.W)
		(min_zoom,max_zoom)=self.map.mapServer.getZoom()
		(sx,sy)=self.map.getOffscreenSize()
		mode=[]
		for (s,z) in [("Current",0),("High",1),("Very high",2)]:
			if max_zoom>=self.map.zoom+z:
				mode.append(("%s resolution (%d x %d pixels, z=%d)" % (s,sx*(z+1),sy*(z+1),self.map.zoom+z),z))
		for (txt,v) in mode:
			b=tkinter.Radiobutton(self,text=txt,variable=self.zoomVar,value=v,command=self.setzoom)
			b.pack(anchor=tkinter.W)
		l=tkinter.Label(self,textvariable=self.filevar,font=("Arial",10))
		l.pack()
		fb=tkinter.Button(self,text="Select image's name",command=self.choosefile)
		fb.pack()
		l=tkinter.Label(self,text="WARNING : Respect licences and usage",font=("Arial",12,'bold'))
		l.pack()
		m=tkinter.Message(self,text=licence,font=("Arial",10),width=350)
		m.pack()
		b=tkinter.Button(self,text="OK",command=self.ok)
		b.pack(side=tkinter.RIGHT,pady=10,padx=5)
		b=tkinter.Button(self,text="Cancel",command=self.cancel)
		b.pack(side=tkinter.RIGHT,pady=10,padx=5)
		# bind action buttons
		self.bind("<Return>",self.ok)
		self.bind("<Escape>",self.cancel)
		
	def setzoom(self):
		self.zoommod=self.zoomVar.get()
		
	def choosefile(self):
		default=os.path.basename(self.filename)
		self.filename=tkinter.filedialog.asksaveasfilename(initialfile=default,defaultextension='.png',title="Save actual map")
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
		
		
class SearchDialog(tkinter.Toplevel):
	""" Handle dialog window to search geographic location
	"""
	def __init__(self,parent,map,title=None,query="",results=[]):
		tkinter.Toplevel.__init__(self,parent)
		self.transient(parent)
		if title:
			self.title(title)
		self.map=map
		self.query=query
		self.parent=parent
		self.results=results
		self.location=None
		self.zoom=0
		body=tkinter.Frame(self)
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
		m=tkinter.Message(self,text="Search location using Nominatim service",font=("Arial",12,"bold"),width=350)
		m.pack()
		r=tkinter.Frame(self)
		l=tkinter.Label(r,text="Query:")
		self.q=tkinter.Entry(r,width=50)
		b=tkinter.Button(r,text="Search",command=self.search)
		l.grid(row=0,column=0)
		self.q.grid(row=0,column=1)
		b.grid(row=0,column=2)
		r.pack()
		r=tkinter.Frame(self)
		self.rListLabel=tkinter.Label(r,text="Result(s)",anchor=tkinter.W,font=("Arial",12,'bold'))
		self.rScroll=tkinter.Scrollbar(r,orient=tkinter.VERTICAL)
		self.rList=tkinter.Listbox(r,width=80,height=12,relief=tkinter.RIDGE,yscrollcommand=self.rScroll.set,font=("Arial",11))
		self.rListLabel.grid(row=0,column=0,sticky=tkinter.NW)
		self.rList.grid(row=1,column=0,sticky=tkinter.N+tkinter.S)
		self.rScroll.grid(row=1,column=1,sticky=tkinter.N+tkinter.S+tkinter.W)
		r.pack()
		self.bOk=tkinter.Button(self,text="OK",command=self.ok,state=tkinter.DISABLED)
		self.bOk.pack(side=tkinter.RIGHT,pady=10,padx=5)
		b=tkinter.Button(self,text="Cancel",command=self.cancel)
		b.pack(side=tkinter.RIGHT,pady=10,padx=5)
		
		# bind action buttons
		self.rList.bind("<<ListboxSelect>>",self.on_result_select)
		self.rScroll.configure(command=self.rList.yview)
		self.bind("<Return>",self.ok)
		self.bind("<Escape>",self.cancel)
		#
		self.q.delete(0,tkinter.END)
		self.q.insert(0,self.query)
		self.buildResultsList()
	
	def buildResultsList(self):
		self.rList.delete(0,tkinter.END)
		for r in self.results:
			self.rList.insert(tkinter.END,"(%s) %s" % (r.type,r.name))
	
	def search(self,event=None):
		self.query=self.q.get()
		q=bigtilemap_nominatim.query_url(self.query.split())
		q.download()
		self.results=q.xml_parse(self.map)
		self.buildResultsList()
		self.bOk.config(state=tkinter.DISABLED)
	
	def on_result_select(self,event=None):
		sel=event.widget.curselection()
		if sel:
			id=int(sel[0])
			self.location=self.results[id].location
			self.zoom=self.getZoom(self.results[id].box)
			self.bOk.config(state=tkinter.NORMAL)
		else:
			self.location=None
			self.zoom=0
			self.bOk.config(state=tkinter.DISABLED)
		
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
		
	def getZoom(self,box=None):
		""" best zoom to make visible the box area """
		wsize=self.map.getWidgetSize()
		zoom=self.map.mapServer.getBestZoom(box,wsize)
		return zoom

# -- Main -------------------------
def main(sargs):
	print("-- %s %s ----------------------" % (__application__,__version__))
	if len(bigtilemap.tile_servers)>0:
		# load config
		cfg=AppConfig(config.pmx_db_file)
		cfg.loadParams()
		cfg.loadResults()
		# Start the GUI
		w=tkinter.Tk()
		i=main_gui(w,cfg)
		w.mainloop()
	else:
		print("error : no map servers defined")

#this calls the 'main' function when this script is executed
if __name__ == '__main__': 
	main(sys.argv[1:])
