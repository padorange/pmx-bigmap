#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" bigmap_nominatim
	----------------
	Nominatim class for pmx/bigmap application
	Query web service (Nominatim) to retrive a geographical list of result
	Query is a simple string.
	Nominatim is a OpenStreetMap service, data are licenced under OdBL licence
	More about Nominatim : http://wiki.openstreetmap.org/wiki/Nominatim
	Usage policy : http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy
"""

__author__="Pierre-Alain Dorange"
__contact__="pdorange@mac.com"
__copyright__="Copyright 2016, Pierre-Alain Dorange"
__license__="BSD"
__version__="0.2"

# standard modules
import os.path
import urllib2,socket
import sys
import getopt
import xml.etree.ElementTree as ET

# local modules
import bigmap

# constants & globals
base_url="http://nominatim.openstreetmap.org/search?"
query_tag="q="
format_tag="format="
polygon_tag="polygon="
address_tag="addressdetails="
country_tag="countrycodes="
lang_tag="accept-language="
format_list=("xml","html","json")

default_country=None
default_format="xml"
default_polygon="1"
default_address="1"
default_input=None
default_output=None

class osm_object():
	""" OSM object retrieved from Nominatim
		id : OSM unique id (see Core Elements : http://wiki.openstreetmap.org/wiki/Elements)
		osm_type : OSM object type (node, way or relation)
		familly : OSM class
		type : Nominatim place type
		name : Nominatim displayed name (full OSM name)
		place_id : Nominatim ID
		lon, lat : geographic coordinates
		box : bounding box geo coordinates (lon,lat)-(lon,lat)
		zoom : proposed zoom level, according to box
	"""
	def __init__(self,id=-1):
		self.id=id
		self.osm_type=""
		self.location=bigmap.Coordinate(0.0,0.0)
		self.box=None
		self.zoom=0
		self.place_id=-1
		self.familly=""
		self.type=""
		self.name=""
		
	def parse_nominatim(self,raw_place,map=None):
		""" parse a XML result (one place per result)à
			extract data from result and try building a better name (than default one)
		"""
		place=raw_place.attrib
		self.id=int(place['osm_id'])
		self.place_id=int(place['place_id'])
		self.name=place["display_name"]
		self.familly=place["class"]
		self.type=place["type"]
		self.osm_type=place["osm_type"]
		self.location=bigmap.Coordinate(float(place["lon"]),float(place["lat"]))
		try:
			box=place["boundingbox"].split(',')
			(zmmin,zmmax)=self.mapServer.getZoom()
			if box[0]==box[1] and box[2]==box[3]:
				self.box=None
				self.zoom=zmmax
			else:
				up=bigmap.Coordinate(float(box[2]),float(box[0]))
				down=bigmap.Coordinate(float(box[3]),float(box[1]))
				self.box=bigmap.BoundingBox(up,down)
				dlon=self.box.rightdown.lon-self.box.leftup.lon
		except:
			self.box=None
			self.zoom=0
		# try building a simpler-better name (than display_name)
		name=""
		prefix=""
		i=0
		for item in raw_place:
			if item.tag==self.type:
				name=name+prefix+item.text
				i=i+1
				prefix=", "
			elif item.tag==u'house_number':
				name=name+prefix+item.text
				i=i+1
				prefix=", "
			elif item.tag==u'road':
				name=name+prefix+item.text
				i=i+1
				prefix=", "
			elif item.tag==u'city' or item.tag==u'town' or item.tag==u'village':
				name=name+prefix+item.text
				i=i+1
				prefix=", "
			elif item.tag==u'country':
				name=name+prefix+item.text
				i=i+1
				prefix=", "
		if i>=3:
			self.name=name
		print "result",self.name,"b:",self.box,"az:",self.zoom
	
	def __str__(self):
		str="%s/%s: %s\n\t%s" % (self.familly,self.type,self.location,self.name)
		if self.box:
			str=str+"\n\t%s" % self.box
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
	"""
	def __init__(self,args,lang=None):
		self.url=None
		self.data=None
		query=""
		prefix=""
		for a in args:
			a.replace('+','')
			query=query+prefix+a
			prefix="+"
		self.url="%s%s%s" % (base_url,query_tag,query)
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
		print self.url
		
	def download(self):
		""" Download the XML results
		"""
		try:
			headers={'User-Agent':self.user_agent}
			request=urllib2.Request(self.url,None,headers)
			stream=urllib2.urlopen(self.url, None)
			if stream:
				self.data=stream.read()
				stream.close()
				print "QUERY:",self.url
				print "RESPONSE:",self.data
				print "----"
		except:
			print "error can't load over internet : ",sys.exc_info()
			print self.url

	def xml_parse(self,map=None):
		""" Parse the Nominatim XML results to build a simple osm_object list
		"""
		results=[]
		try:
			root=ET.fromstring(self.data)
			print root.attrib['attribution']
			if len(root)>0:
				for raw_result in root:	# parse each individual result
					if raw_result.tag=='place':
						result=osm_object()
						result.parse_nominatim(raw_result,map)
						results.append(result)
		except:
			print "error can't parse XML : ",sys.exc_info()
			result=osm_object()
			result.name=sys.exc_info()
			result.type='error'
			results=[result]
		return results

def usage():
	print "%s %s" % (__file__,__version__)
	print "------------------------------------------"
	print "\t-h : help"
	print "\t-f : format (xml,html or json)"
	print "\t-c : specify a country (fr, gb, de...)"
	print "\t-i : input file with list of adresses"
	print "\t-o : output file for coordinates"
	print
	
def main(argv):
	"""
		Main :
		handle command line arguments and launch appropriate processes
	"""
	global default_input,default_output
	
	print '-------------------------------------------------'
		
	# extract and parse command line arguments to determine parameters and arguments
	try:
		opts,args=getopt.getopt(argv,"hc:f:i:o:",["help","country=","format=","input=","output="])
	except:
		usage()
		sys.exit(2)
	for opt,arg in opts:	# parse arguments
		if opt in ("-h","--help"):
			usage()
		elif opt in ("-c","--country"):
			default_country=arg
		elif opt in ("-f","--format"):
			default_format=arg
		elif opt in ("-i","--input"):
			default_input=arg
		elif opt in ("-o","--output"):
			default_output=arg
	result=""
	if default_input:	# if input file, take arguments from him
		file=open(default_input,'r')
		for line in file:
			str=line.decode('UTF-8')
			line=line.replace("\n","")
			line=line.replace("\r","")
			url=query_url(line.split())
			url.download()
			url.xml_parse()
			if default_output:
				result=result+url.ol_export()
		file.close()
	else:				# otherwise take arguments from command line
		if len(args)==0:
			usage()
			sys.exit(2)
		url=query_url(args)
		url.download()
		r=url.xml_parse()
		print r
		if default_output:
			result=result+url.ol_export()
	if default_output:	# store result in output text file (if needed)
		f=open(default_output,"w")
		f.write(result.encode('UTF-8'))
		f.close()

if __name__ == '__main__' :
	main(sys.argv[1:])