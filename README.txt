
pmx.py
---------------------------------------------------------------------------------------------
New-BSD Licence, (c) 2010-2016, Pierre-Alain Dorange
http://www.leretourdelautruche.com/pmwiki/index.php/Autruche/BigMap
---------------------------------------------------------------------------------------------
pmx.py is an application to explore map using online TMS services.
It was build on bigmap.py library (see below). 
It use Tkinter cross-platform for GUI and PIL/Pillow for image handling.

-- usage ------------------------------------------------------------------------------------

python pmx.py

*********************************************************************************************

bigmap.py
---------------------------------------------------------------------------------------------
New-BSD Licence, (c) 2010-2016, Pierre-Alain Dorange
http://www.leretourdelautruche.com/pmwiki/index.php/Autruche/BigMap
---------------------------------------------------------------------------------------------
bigmap.py is a python script that allow user to build map from terminal using TMS services.
TMS are TileMapService, providing map from small tiles.
bigmap.py download tiles from TMS and assemble them into a bigger map.

Assemble tiles with PIL/Pillow library (separate install)
Supported TMS are describe into servers.ini file (read thanks to ConfigObj).

bigmap.py require :
	Python 2.5.x / 2.7.x
	PIL (or Pillow) library for Python
	ConfigObj (included)

Read carefully licences and notes before using, not all maps have the same licence and usage policy.

-- usage ------------------------------------------------------------------------------------

python bigmap.py [parameters]
	-h (--help)	: get help
	-d (--display)  : display list of supported servers
	-o (--output)	: specify output file name
	-s (--server)	: define tile servers, default is osm.mapnik 
			  (beginning with * define a partial name, ie *osm return all ohm rendering)
	-z (--zoom)	: define zoom level (-z[z])
	-b (--box)	: define bounding box (longitude,latitude,longitude,latitude) 
			  (-b[x],[y],[x],[y])
	-l (--location) : define location longitude,latitude, must be associated with -t option
	-t (--tile)	: define width and height (meters to assemble, for -l option
			  you can use '*' wildcard for server name
	-n (--name) 	: specify a location name (see location.ini)
	-m (--marker)	: specify a marker description file
	-c (--cache)	: override local cache
	--date		: specify a date, for earthdata (landsat 7) server (YYYY-MM-DD)

Three methods can be used to define the map area to download :
	* classic bound box (corner of a square express in latitude, longitude) and a zoom level : -b -z options
	* a center (latitude, longitude), size (latitude, longitude) and zoom level : -l -t -z options
	* a location name (from predefined location.ini file) : -n -z options
	
To found coordinates, one easy method is to use www.openstreetmap.org, drag the map and zoom according to what you want
Click on "export" (up bar) adjust your view and get the 4 coordinates defining the bounding box :
	ie : 	up-left corner : 48.8711,2.3125
		down-right corner : 48.851,2.33921
		choose a detail-zoom level (16 to 18 par street details, 12-15 for region detail, 8-10 for country detail)
	ie : python bigmap.py -b48.8711,2.3125,48.851,2.33921 -z16
	
Alternavely you can use a center location and choose a width and height around. Use www.openstreetmap.org, drag the map and zoom according to what you want. note the central coordinates and zoom (in the url), then click "export" and note difference between latitude and longitude.
	ie : python bigmap.py -l48.8622,2.3277 -t500,400 -z16

See examples below.

-- Notes ----------------------------------------------------------------------------------

bigmap.py support many tile map servers (TMS) (or slippy map), to have a detailed list (with licence and zoom available) :
	python bigmap.py -d
	
Support many OSM data renderer and some experimental commercial servers (google, bing, landsat...)

bigmap.py respects mapnik tile usage policy : <http://wiki.openstreetmap.org/wiki/Tile_usage_policy>
  - clearly display licence attribution : OdbL for data and CC-BY-SA for renderer 
      see : <http://www.openstreetmap.org/copyright>
  - valid User-Agent identifying application (kHTTP_User_Agent, see below)
  - cache Tile downloads locally
  - maximum of 2 download threads

To respect those recommendations, bigmay.py use a local cache and do not allow for request over 300 tiles per request.
Please respect those usage policy and do not change those parameters.
  	
Cache :
bigmap.py use a local cache to store individual tiles, is you need to refresh local data, simply trash to cache folder
or use -c option to reload tiles
Cache folder can rapidly became big and occupy lot of space on your hard-drive.
The actual cache size if displayed at each run and is limited by k_cache_max_size parameter (default is 20 MB).
Tile are consider up-to-date for k_cache_delay seconds (default is 96 hours)

Parameters :
Main parameters are defined into config.py file.

-- Warning ---------------------------------------------------------------------------------
 
Use it with respect to Tile Server usage policy : do not download large area at high zoom and do not use it too often.
Remember tile servers are not intend for local usage but for online browser usage.

Do not forget to clearly display licence on final map/usage : <http://www.openstreetmap.org/copyright>

CloudMade & Mapbox render require using your own API Key (just login to CloudMade and copy the API Key in the source code)

ArcGIS render is not based on OSM and has a different licence : cc-by-sa-nc (add no commercial uses)

Google, Bing or Nokia may not be used for any none-personnal use, read carefully commercial licences, local upload is probably not allowed.

-- Examples --------------------------------------------------------------------------------

French atlantic coast near "La Rochelle" with openmapquest's and cyclemap style
	bigmap.py -b-1.5978,46.3536,-0.9098,45.9411 -z11 -sopenmapquest.road,thunderforest.cyclemap
Public Transport near Edinburgh, rendered with thunderforest transport
	python bigmap.py -b-3.4197,55.9024,-3.2468,55.9761 -z15 -sthunderforest.transport
Forbidden City (Beijing, China), rendered with Stamen's Watercolor
	python bigmap.py -b116.3727,39.9025,116.4019,39.9346 -z16 -sstamen.watercolor
Venise, rendered with acetate (Stamen & ESRI)
	python bigmap.py -b12.32203,45.4249,12.34205,45.43717 -z15 -smapbox.pencil
Aix Island (France), rendered with all satellite view :
	python bigmap.py -b-1.1835,46.0273,-1.1509,46.0062 -z16 -s*satellite
Angkor Wat Temple (Cambodia), rendered with Pencil (from mapbox)
	python bigmap.py -nangkor -smapbox.pencil
Colorful Grand Prismatic Spring (USA), satellite :
	python bigmap.py -ncolorful

-- Tile Servers Supported -------------------------------------------------------------------------

To get actual complete list of tile and server available : python bigmap.py -dw

Main providers (OSM data, free licence):
	OSM : default, fr, de, hot...
	Thunderforest : cyclemap, transport, landscape...
	Stamen : nice graphical rendering like watercolor, toner (with many overlay)
	Mapbox : require an API key, many nice maps from OSM : foursquare, pencil, pirates, edit...
	Acetate : route (and overlay)
	OpenTopoMap : nice topo map
	CartoDB : 
	OpenMapQuest : route
	OpenMapSurfer : general map (with 3D buildings from zoom level) and many overlay
Not OSM data :
	ArcGis : street, topo, terrain, ocean : cc-by-sa-nc licence
	Google : usage restricted see Google licence
	Bing : usage restricted see Microsoft licence
	Nokia : usage restricted see Nokia licence
	Yandex : experimental, usage restricted see Yandex licence
Satellite :
	Bluemarble : NASA satellite assembly of 2004 cloud-free pictures (public domain)
	OpenMapQuest : satellite
	MapBox : source NASA, DigitalGlobe and USGC
	ArcGIS : source NASA, USGC
	Google : usage restricted see Google licence
	Bing : usage restricted see Microsoft licence
	Landsat 7 : time stamped data, experimental, usage restricted see NASA/Landsat 7 licence
		used with --date option
Special Data :
	ITO : provide overlay with special data (electricity, water, railway…)
	OpenWeatherMap : meteo, but still experimental (server seem very slow)
	OpenPort : meteo at high zoom level

-- History --------------------------------------------------------------------------------

see pmx.py and bigmap.py header for a version history
