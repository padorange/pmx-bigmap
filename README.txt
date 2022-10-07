This project is composed of 2 sub-projects :
	pmx.py		a GUI interface to explore maps and made fixed map ready to print
	bigmap.py	a CLI interface to do the same
---------------------------------------------------------------------------------------------
New-BSD Licence, (c) 2010-2021, Pierre-Alain Dorange
git : https://github.com/padorange/pmx-bigmap
web : http://www.leretourdelautruche.com/pmwiki/index.php/Autruche/BigMap
---------------------------------------------------------------------------------------------

This project has for purpose to allow end-user to use maps from web services 
using a CLI or GUI interface (no HTML, no Javascript). Mostly OpenStreetMap maps. 

bigmap is the foundation, can be used as a python script (CLI) to download maps.
pmx is a front-end for bigmap using a simple graphical interface (GUI) via TCL/Tkinter

pmx/bigmap provide config for many Tile Map web services (Tile Map Service : TMS)
The main purpose is to use open source for maps (mainly OpenStreetMap) but some other TMS are
provided (some commercial). Some TMS required an API Key (to identify users).

pmx/bigmap interact with OpenStreetMap (OSM), using main services :
	- base map TMS (or Slippy Map), maps web service
	- Nominatim, geographic search
	- Database, raw geographic data

Please always read carefully licences for each tile map service.
If you reuse this code always display those informations.
OSM license is OdBL for map rendering and data.

See NOTES chapter (below) for detailed informations.

-- History --------------------------------------------------------------------------------

see pmx.py and bigmap.py header for a version history

*********************************************************************************************

pmx.py (GUI)
---------------------------------------------------------------------------------------------

pmx.py is an application to explore maps using online TMS services.
It was build upon bigmap.py library (see below). 
It use Tkinter standard cross-platform for GUI and PIL/Pillow for image handling.

pmx.py display tiles assembled (like online map server), user can browse different server 
and overlay, search geographic locations and export curent map.

pmx.py require :
	Python 2.7.x
	Tkinter library for Python (often already include with default Python)
	Pillow (or PIL) library for Python, handles images (PNG, JPEG...)
	ConfigObj (included)

-- usage ------------------------------------------------------------------------------------

python pmx.py

*********************************************************************************************

bigmap.py (CLI)
---------------------------------------------------------------------------------------------

bigmap.py is a python script (CLI) that allow user to build map from terminal using TMS services.
TMS are TileMapService, providing map from small tiles.
bigmap.py download tiles from TMS and assemble them into a bigger map.

Assemble tiles with PIL/Pillow library (separate install)
Supported TMS are describe into servers.ini file (read thanks to ConfigObj).

bigmap.py include bigmap_nominatim.py a small module to make request to OSM/Nominatim service.
Nominatime allow to make geographic request to find locations.

bigmap.py require :
	Python 2.7.x
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
	-f (—find)	: specify a request to be used via Nominatim service (return a geographical location)
	-m (--marker)	: specify a marker description file
	-c (--cache)	: override local cache
	--date		: specify a date, for earthdata (landsat 7) server (YYYY-MM-DD)

Four methods can be used to define the map area to download :
	* classic bound box (corner of a square express in latitude, longitude) and a zoom level, using options : -b -z
	* a center (latitude, longitude), size (latitude, longitude) and zoom level, sugin options : -l -t -z
	* a location name (from predefined location.ini file), using options : -n -z
	* a Nominatim query, options : -f -z

To found coordinates, one easy method is to use www.openstreetmap.org, drag the map and zoom according to what you want
Click on "export" (up bar) adjust your view and get the 4 coordinates defining the bounding box :
	ie : 	up-left corner : 48.8711,2.3125
		down-right corner : 48.851,2.33921
		choose a detail-zoom level (16 to 18 par street details, 12-15 for region detail, 8-10 for country detail)
	ie : python bigmap.py -b48.8711,2.3125,48.851,2.33921 -z16

-- Examples --------------------------------------------------------------------------------

French atlantic coast near "La Rochelle" using a box, rendering with openmapquest's and cyclemap style
	bigmap.py -b-1.5978,46.3536,-0.9098,45.9411 -z11 -sopenmapquest.road,thunderforest.cyclemap

Public Transport near Edinburgh using a box, rendered with thunderforest transport
	python bigmap.py -b-3.4197,55.9024,-3.2468,55.9761 -z15 -sthunderforest.transport

Forbidden City (Beijing, China) using a box, rendered with Stamen's Watercolor map design
	python bigmap.py -b116.3727,39.9025,116.4019,39.9346 -z16 -sstamen.watercolor

Venizia using Nominatim, rendered with MapBox’s Pencil style
	python bigmap.py -fVenezia -z12 -smapbox.pencil

Aix Island (France) using Nominatim, rendered with all satellite view :
	python bigmap.py -f«Ile d’Aix» -z16 -s*satellite

Angkor Wat Temple (Cambodia), rendered with Pencil (from mapbox)
	python bigmap.py -nangkor -smapbox.pencil

Colorful Grand Prismatic Spring (USA), satellites :
	python bigmap.py -ncolorful

*********************************************************************************************

-- Notes ----------------------------------------------------------------------------------

bigmap/pmx support many Tile Map Servers (TMS) or slippy map, to have a detailed list (with licence and zoom available) :
	python bigmap.py -d

Support for many OSM data renderer and some experimental commercial servers (google, bing, yandex...)

bigmap/pmx respects mapnik tile usage policy : <http://wiki.openstreetmap.org/wiki/Tile_usage_policy>
meaning :
  - clearly display licence attribution : OdbL for data and CC-BY-SA for renderer 
      see : <http://www.openstreetmap.org/copyright>
  - valid User-Agent identifying application (kHTTP_User_Agent, see below)
  - cache Tile downloads locally (7 days recommended)
  - maximum of 2 download threads

To respect those recommendations, bigmay/pmx use a local cache and do not allow for request over 300 tiles per request.

Please respect those usage policy and do not change those parameters. 
Disrespect for usage policy often lead to be banned from TMS.
Be banned from TMS service was made regarding User-Agent referrer, so if you're banned, all bigmap/pmx users were also banned.

Cache :
bigmap.py use a local cache to store individual tiles, if you need to refresh local data, simply trash to cache folder
or use -c option (reset cache)
Cache folder can rapidly became big and occupy lot of space on your hard-drive.
The actual cache size if displayed at each run and is limited by k_cache_max_size parameter (default is 100 MB).
Tile are consider up-to-date for k_cache_delay seconds (default is 96 hours)

Parameters :
Main parameters are defined into config.py file.

-- Warning ---------------------------------------------------------------------------------

Use it with respect to Tile Server usage policy : 
	do not download large area at high zoom and do not use it too often.
Remember tile servers are not intend for local usage but for online browser usage.

Do not forget to clearly display licence on final map/usage :
	for osm : <http://www.openstreetmap.org/copyright>

Some TMS require using your own API Key (ie. MapBox, Lyrk, Here rendering).
For those services you have to get an API key and copy it into the configuration file : api_key.ini

ArcGIS render is not based on OSM and has a different licence : cc-by-sa-nc (add no commercial uses)

Google, Bing or Nokia may not be used for any none-personnal use, read carefully commercial licences, local upload is probably not allowed. Using mpx/bigmap with google often lead to be banned after some minutes.

-- Tile Servers Supported -------------------------------------------------------------------------
To get actual complete list of tile and server available : python bigmap.py -d
TMS are configured in servers.ini file.

Main providers (OSM data : free & open licence):
	OSM : default, fr, de, hot...
	Thunderforest : cyclemap, transport, landscape...
	Stamen : nice graphical rendering like watercolor, toner (with many overlay)
	Mapbox : require an API key, many nice maps from OSM : foursquare, pencil, pirates, edit...
	OpenTopoMap : nice topo map
	CartoDB : nice clean map with overlays
	OpenMapSurfer : general map (with 3D buildings from zoom level) and many overlay

Not OSM data but free & open licence (commercial restrictions) :
	ArcGis : street, topo, terrain, ocean : cc-by-sa-nc licence

Satellite :
	Bluemarble : NASA satellite assembly of 2004 cloud-free pictures (public domain)
	MapBox : source NASA, DigitalGlobe and USGC
	ArcGIS : source NASA, USGC
	Google : usage restricted see Google licence
	Bing : usage restricted see Microsoft licence

Special Data :
	ITO : provide overlay with special data (electricity, water, railway...)
	OpenWeatherMap : meteo, but still experimental (server seem very slow)
	OpenPort : meteo at high zoom level
	Gibs (NASA) : time stamped data, experimental, usage restricted see NASA/GIBS licence
		used with --date option
		display satelite images and scientific data once per day

Not open licence (commercial services, may not works always fine)
	Google : usage restricted see Google licence
	Bing : usage restricted see Microsoft licence
	Nokia : usage restricted see Nokia licence
	Here : usage restricted see Nokia licence
	Yandex : experimental, usage restricted see Yandex licence

-- Search service ------------------------------------------------------------------------------

Search services provide by OpenStreetMap's Nominatim service : 
	<http://wiki.openstreetmap.org/wiki/Nominatim>
Based on OSM data.
Can be used with bigmap (-s option) or bigmap_nominatim or pmx ; also provide reverse-search.
Detailed information about Nominatim : 
	<http://wiki.openstreetmap.org/wiki/Nominatim>
	<http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy>

Nominatim better work with request build from left to right using detail (left) and country (right).
Using comma improve performance (making query less complex).

A good example :
	12 baker street, london, england
poor example (but works)
	baker street london
bad example 
	baker street

-- Configuration --------------------------------------------------------------------------------

pmx/bigmap use configuration files (store in the source directory)
	* servers.ini	describe TMS supported
	* location.ini	describe some default location
	* api_key.ini	describe api key for TMS requiring access key
	* resource		directory with some pictures for pmx GUI
pmx/bigmap store user data in the default system user directory (home) :
	* pmx.db		store user config (window size, default TMS, last search...)
	* cache			store cached Tile from TMS (see cache above)

-- End note -------------------------------------------------------------------------------------

Thanks to all OpenStreetMap contributors for the data, software and services provided
Thanks for Guido van Rossum for providing Python
