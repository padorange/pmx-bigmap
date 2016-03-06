#!/usr/bin/env python
# -*- coding: utf-8 -*-

import bigmap

locs=((32.15017,-110.83381),)
size=(0.001,0.001)
z=18
server_name="google.satellite"

api_keys=bigmap.LoadAPIKey("api_key.ini")
tile_servers=bigmap.LoadServers("servers.ini")

for loc in locs:
	upleft=bigmap.Coordinate(loc[0],loc[1])
	(xwidth,ywidth)=size
	centered=True
	zoom=z

	if (centered):
		downright=bigmap.Coordinate(upleft.x+xwidth,upleft.y+ywidth)
		upleft=bigmap.Coordinate(upleft.x-xwidth,upleft.y-ywidth)

	box=bigmap.BoundingBox(upleft,downright)
	print "------------------------------------------------------------------"
	print "Getting tile(s) for",box,"at zoom %d from %s" % (zoom,server_name)

	server=None
	for s in tile_servers:
		if s.name==server_name:
			server=s

	if s:
		(tile0,tile1)=box.convert2Tile(server,zoom)
		print tile0
		print tile1
		x0=int(tile0[0]+0.5)
		y0=int(tile0[1]+0.5)
		x1=int(tile1[0]+0.5)
		y1=int(tile1[1]+0.5)
		nt=(x1-x0+1)*(y1-y0+1)
		print "(%d,%d)-(%d,%d) : %d tile(s)" % (x0,y0,x1,y1,nt)
		(x0,y0)=bigmap.ll2tile((box.upleft.x,box.upleft.y),zoom)
		(x0,y0)=bigmap.ll2tile((box.downright.x,box.downright.y),zoom)
		nt=(x1-x0+1)*(y1-y0+1)
		print "(%d,%d)-(%d,%d) : %d tile(s)" % (x0,y0,x1,y1,nt)
