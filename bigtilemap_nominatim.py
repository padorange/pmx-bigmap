#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" bigtilemap_nominatim
	----------------
	What it is : 
	Class for pmx/bigtilemap application/script to used with OSM's Nominatim service
	
	What it do : 
	Query web service (Nominatim) to retrieve a geographical list of result
	from a simple string. ie : Baker Street, London
	
	Nominatim is a OpenStreetMap (OSM) service
	Data retrived are licenced under OdBL licence.
	
	More about Nominatim : 
		http://wiki.openstreetmap.org/wiki/Nominatim
	Usage policy : 
		https://operations.osmfoundation.org/policies/nominatim/
	
	history:
	0.4 : 	better error handling
			better request handling
			adding a result list handler
			remove for 'format' option, only support XML
	0.5 : go to python 3
"""

__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"
__copyright__="Copyright 2018-2022, Pierre-Alain Dorange"
__license__="BSD"
__version__="0.5"

# standard modules
import os.path, sys, getopt
import socket
import xml.etree.ElementTree as ET
if sys.version_info.major==2:			# python 2.x
	import urllib2
	urllib2.install_opener(urllib2.build_opener())		# just to disable a bug in MoxOS X 10.6 : force to load CoreFoundation in main thread
else:									# python 3.x
	import urllib.request,urllib.error,urllib.parse

# local modules
import bigtilemap

# trick to made utf-8 default encoder/decoder (python 2.x)
if sys.version_info.major==2:
	reload(sys)
	sys.setdefaultencoding('utf8')

# constants & globals
_debug=False
_debug_raw=False

base_url="http://nominatim.openstreetmap.org/search?"
query_tag="q="
format_tag="format="
format_list=("xml","html","json")
polygon_tag="polygon="
address_tag="addressdetails="
country_tag="countrycodes="
lang_tag="accept-language="

default_format="xml"
default_country=None
default_polygon=None
default_address=None
default_input=None
default_output=None

class osm_object():
	""" OSM object retrieved from Nominatim
			id : OSM unique id (see Core Elements : http://wiki.openstreetmap.org/wiki/Elements)
			attrib : the attribution string (copyright)
			osm_type : OSM object type : node, way or relation
			familly : OSM tag : ie. boundary, place, highway...
			type : OSM value for tag : administrative, town, village, residential...
			name : Nominatim displayed name (full OSM name)
			fullname : Full name rebuild from address details (whenever possible)
			place_id : Nominatim ID
			rank : the Nominatim rank
			importance : the Nominatim importance
			lon, lat : geographic coordinates
			box : bounding box geo coordinates (lon,lat)-(lon,lat) (if available)
			house : house number (if available)
			road : road name (if available)
			city : city name (if available)
			state : state name (if available)
			country : country name (if available)
	"""
	def __init__(self,id=-1):
		self.id=id
		self.attrib=""
		self.osm_type=""
		self.location=bigtilemap.Coordinate(0.0,0.0)
		self.box=None
		self.place_id=-1
		self.rank=-1
		self.importance=0.0
		self.familly=""
		self.type=""
		self.name=""
		self.fullname=""
		self.house=""
		self.road=""
		self.postcode=""
		self.city=""
		self.state=""
		self.country=""
		
	def parse_nominatim(self,raw_place,map=None):
		""" parse a XML result (one place per result)
			extract relevant data from individual result 
			and try building a better name (than default one)
		"""
		place=raw_place.attrib
		self.id=int(place['osm_id'])
		self.place_id=int(place['place_id'])
		self.rank=int(place['place_rank'])
		self.importance=float(place['importance'])
		self.name=place["display_name"]
		self.familly=place["class"]
		self.type=place["type"]
		self.osm_type=place["osm_type"]
		self.location=bigtilemap.Coordinate(float(place["lon"]),float(place["lat"]))
		try:
			box=place["boundingbox"].split(',')
			if box[0]==box[1] and box[2]==box[3]:
				self.box=None
			else:
				up=bigtilemap.Coordinate(float(box[2]),float(box[0]))
				down=bigtilemap.Coordinate(float(box[3]),float(box[1]))
				self.box=bigtilemap.BoundingBox(up,down)
		except:
			self.box=None
		# try building a simpler-better name (than display_name)
		name=u""
		prefix=u""
		i=0
		for item in raw_place:		# try to extract as many address information as possible
			if item.tag==self.type:
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
			elif item.tag==u'house_number':
				self.house=item.text
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
			elif item.tag==u'road':
				self.road=item.text
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
			elif item.tag==u'postcode':
				self.postcode=item.text
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
			elif item.tag==u'city' or item.tag==u'town' or item.tag==u'village':
				self.city=item.text
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
			elif item.tag==u'state':
				self.state=item.text
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
			elif item.tag==u'country':
				self.country=item.text
				name=name+prefix+item.text
				i=i+1
				prefix=u", "
		if i>=2:
			self.fullname=name
		else:
			self.fullname=self.name
		if _debug: print(self)
	
	def __str__(self):
		str=u"%s/%s (rank:%d, importance:%.4f)" % (self.familly,self.type,self.rank,self.importance)
		str=str+u"\n\tname: %s" % self.name
		str=str+u"\n\tloc: %s" % self.location
		if self.box:
			str=str+u"\n\tbox: %s" % self.box
		if self.fullname!=self.name:
			str=str+u"\n\tfname: %s" % self.fullname
			str=str+u"\n\t\thouse: %s" % self.house
			str=str+u"\n\t\troad: %s" % self.road
			str=str+u"\n\t\tcity: %s %s" % (self.postcode,self.city)
			str=str+u"\n\t\tstate: %s" % self.state
			str=str+u"\n\t\tcountry: %s" % self.country
		return str

class osm_list():
	""" list of osm_object with an attribution (copyright)
	"""
	def __init__(self,attrib=u""):
		self.attrib=attrib
		self.list=[]
		
	def append(self,obj):
		if isinstance(obj,osm_object):
			self.list.append(obj)
			if _debug: print("list as %d object(s)" % len(self.list))
		else:
			print("** error : cant add a non-osm_onject to the list")
	
	def __len__(self):
		return len(self.list)
		
	def __getitem__(self,i):
		return self.list[i]
	
	def __str__(self):
		str=self.attrib
		str=str+u"\n"+u"%d result(s):" % len(self.list)
		for r in self.list:
			str=str+u"\n"+r.__str__()
		return str

class query_url():
	""" Query class : query Nominatim for a geographical list of results
		see : http://wiki.openstreetmap.org/wiki/Nominatim
		tags :
			q : 				the query (text with + separator)
			format :			result format (xml, html or json)
			polygon :			1 for boundingbox and polygon coordinates
			addressdetails :	1 for postal address details
			country :			specify the country
		init : create the query
		doawnload : launch the query to Nominatim and doawnload the raw result (xml)
		xmlparse : analyze the raw result and build a list of osm_objects result
	"""
	def __init__(self,args,lang=None):
		""" Create a Nominatim query usign args as a list of element to build the query
			and the global config (using global variables)
		"""
		self.url=None
		self.data=None
		query=""
		prefix=""
		for a in args:
			a=a.replace(' ','+')	# remove spaces
			query=query+prefix+a
			prefix="+"
		self.url='%s%s"%s"' % (base_url,query_tag,query)
		if default_format:
			self.url=self.url+"&%s%s" % (format_tag,default_format)
		if default_polygon:
			self.url=self.url+"&%s%s" % (polygon_tag,default_polygon)
		if default_address:
			self.url=self.url+"&%s%s" % (address_tag,default_address)
		if default_country:
			self.url=self.url+"&%s%s" % (country_tag,default_country)
		if lang:
			self.url=self.url+"&%s%s" % (lang_tag,lang)
		self.user_agent="%s/%s" % (__file__,__version__)

	def __str__(self):
		return self.url
		
	def download(self):
		""" Download the XML results : send query and download raw result"""
		err=1
		try:
			headers={'User-Agent':self.user_agent}
			request=urllib.request.Request(self.url,None,headers)
			stream=urllib.request.urlopen(request)
			if stream:
				self.data=stream.read()
				stream.close()
				print("QUERY:",self.url)
				if _debug_raw: print("RESPONSE:",self.data)
				print("----")
				err=0
			else:
				print("** No Stream")
		except urllib.error.HTTPError as e:
			print("** HTTP Error:",e.code)
			print("HEADER:",headers)
			print("QUERY:",self.url)
			print(e.read())
		except:
			print("** error can't load over internet : ",sys.exc_info())
			print("HEADER:",headers)
			print("QUERY:",self.url)
		return err

	def xml_parse(self,map=None):
		""" Parse the Nominatim XML results to build a simple osm_object list with interpreted results
			using ElementTree library
		"""
		results=osm_list()
		try:
			root=ET.fromstring(self.data)
			results.attrib=root.attrib['attribution']
			if len(root)>0:
				for raw_result in root:	# parse each individual result and retrieve "place"
					if raw_result.tag=='place':
						r=osm_object()
						r.parse_nominatim(raw_result,map)
						results.append(r)
		except:
			print("error can't parse XML : ",sys.exc_info())
			result=osm_object()
			result.name=sys.exc_info()
			result.type='error'
			results=osm_list("error")
			results.append(result)
		return results

def usage():
	print("%s %s" % (__file__,__version__))
	print("------------------------------------------")
	print("\t-h : help")
	print("\t-p : return polygon if value is '1'")
	print("\t-a : return full address if value is '1'")
	print("\t-c : specify a country (fr, gb, de...)")
	print("\t-i : input file with list of adresses")
	print("\t-o : output file for coordinates")
	print()
	
def main(argv):
	""" Main :
		handle command line arguments and launch appropriate processes
	"""
	global default_input,default_output,default_polygon,default_address,default_country
	
	print('-------------------------------------------------')
		
	# extract and parse command line arguments to determine parameters and arguments
	try:
		opts,args=getopt.getopt(argv,"hpac:i:o:",["help","polygon","address","country=","input=","output="])
	except:
		usage()
		sys.exit(2)
	for opt,arg in opts:	# parse arguments
		if opt in ("-h","--help"):
			usage()
		elif opt in ("-c","--country"):
			default_country=arg
		elif opt in ("-p","--polygon"):
			default_polygon="1"
		elif opt in ("-a","--address"):
			default_address="1"
		elif opt in ("-i","--input"):
			default_input=arg
		elif opt in ("-o","--output"):
			default_output=arg
	result=""
	results=[]
	if default_input:	# if input file, take arguments from him
		file=open(default_input,'r')
		for line in file:
			str=line.decode('UTF-8')
			line=line.replace("\n","")
			line=line.replace("\r","")
			url=query_url(line.split())
			if url.download()==0:
				results=url.xml_parse()
				if default_output:
					result=result+url.ol_export()
		file.close()
	else:				# otherwise take arguments from command line
		if len(args)==0:
			usage()
			sys.exit(2)
		url=query_url(args)
		if url.download()==0:
			results=url.xml_parse()
			if default_output:
				result=result+url.ol_export()
	if default_output:	# store result in output text file (if needed)
		f=open(default_output,"w")
		f.write(result.encode('UTF-8'))
		f.close()
	else:
		print(results)

if __name__ == '__main__' :
	main(sys.argv[1:])
