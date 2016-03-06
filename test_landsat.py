#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib2,socket

data=None
user_agent="bigmap.py 0.9"
tile_url='http://map1a.vis.earthdata.nasa.gov/wmts-webmerc/VIIRS_CityLights_2012/default/GoogleMapsCompatible_Level8/8/128/91.jpg'
headers={'User-Agent':user_agent}
request=urllib2.Request(tile_url,None,headers)
socket.setdefaulttimeout(120)
stream=urllib2.urlopen(tile_url)
header=stream.info()
content=header.getheaders("Content-Type")
data=stream.read()
stream.close()