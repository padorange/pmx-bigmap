This project is composed of 2 sub-projects :

* pmx.py, a GUI interface to explore maps and made fixed map ready to print
* bigtilemap.py, a CLI interface to do the same

Licence : New-BSD Licence, (c) 2010-2024, Pierre-Alain Dorange

Liens :

* git : https://github.com/padorange/pmx-bigmap
* web : http://www.leretourdelautruche.com/pmwiki/index.php/Autruche/BigMap

This project has for purpose to allow end-user to use maps from web services using a CLI or GUI interface (no HTML, no Javascript). Mostly OpenStreetMap maps.

bigtilemap.py is the foundation, can be used as a python script (CLI) to download maps.
pmx is a front-end for bigmap using a simple graphical interface (GUI) via TCL/Tkinter

pmx/bigtilemap provides config for many Tile Map web services (Tile Map Service : TMS)
The main purpose is to use open source for maps (mainly OpenStreetMap) but some other TMS are
provided (some commercial). Some TMS required an API Key (to identify users).

pmx/bigtilemap interact with OpenStreetMap (OSM), using main services :

- base map TMS (or Slippy Map), maps web service
- Nominatim, geographic search
- Database, raw geographic data

Please always read carefully licences for each tile map service. If you reuse this code always display those informations.
OSM license is OdBL for map rendering and data.

See NOTES chapter (below) for detailed informations.

-- History --------------------------------------------------------------------------------

see pmx.py and bigtilemap.py headers for a version history

*********************************************************************************************

pmx.py (GUI)
-

pmx.py is an application to explore maps using online TMS services.
It was build upon bigtilemap.py library (see below). 
It use Tkinter for Python (standard cross-platform) as GUI and PIL/Pillow for image handling.

pmx.py display tiles assembled (like online map server), user can browse different servers and overlays, search geographic locations and export maps.

pmx.py require : Python 3.x, Tkinter library for Python (often already include with default Python) and Pillow (ex PIL) library for Python, handles images (PNG, JPEG...)

-- usage ------------------------------------------------------------------------------------

	python3 pmx.py

*********************************************************************************************

bigtilemap.py (CLI)
-

bigtilemap.py is a python script (CLI) that allow user to build map from terminal using TMS services.
TMS are TileMapService, providing map from small tiles.
bigtilemap.py download tiles from TMS and assemble them into a bigger map.

Assemble tiles with PIL/Pillow library (separate install)
Supported TMS are describe into servers.ini file.

bigtilemap.py include bigtilemap_nominatim.py a small module to make request to OSM/Nominatim service.
Nominatim allow to make geographic request to find locations.

bigtilemap.py require :
	Python 3.x
	PIL (ex Pillow) library for Python

Read carefully licences and notes before using, not all maps have the same licence and usage policy.

-- usage ------------------------------------------------------------------------------------

	python3 bigtilemap.py [parameters]

	-h (--help)	: get help
	-d (--display)  : display list of supported servers
	-o (--output)	: specify output file name
	-s (--server)	: define tile servers, default is osm.mapnik 
						(using * (wildcard) define a partial name, ie *osm return all osm rendering)
	-z (--zoom)		: define zoom level (-z[z])
	-b (--box)		: define bounding box (longitude,latitude,longitude,latitude) 
						(-b[x],[y],[x],[y])
	-l (--location) : define location longitude,latitude, must be associated with -t option
	-t (--tile)		: define width and height (meters to assemble, for -l option
	-n (--name) 	: specify a location name (see location.ini)
	-f (--find)		: specify a request to be used via Nominatim service (return a geographical location)
	-m (--marker)	: specify a marker description file
	-c (--cache)	: override local cache
	--date			: specify a date, for earthdata (landsat 7) server (YYYY-MM-DD)

Define geographic coordinates

Four methods can be used to define the map area to download :

* classic bound box (corner of a square express in latitude, longitude) and a zoom level, using options : -b -z
* a center (latitude, longitude), size (latitude, longitude) and zoom level, using options : -l -t -z
* a location name (from predefined location.ini file), using options : -n -z
* a Nominatim query, using options : -f -z

To found coordinates, one easy method is to use www.openstreetmap.org, drag the map and zoom according to what you want
Click on "export" (up bar) adjust your view and get the 4 coordinates defining the bounding box :
	ie : 	up-left corner : 48.8711,2.3125
			down-right corner : 48.851,2.33921
			choose a detail-zoom level
				16 to 18 for street details, 
				12-15 for region detail, 
				8-10 for country detail)
	ie : python3 bigtilemap.py -b48.8711,2.3125,48.851,2.33921 -z16

-- Examples --------------------------------------------------------------------------------

French atlantic coast near "La Rochelle" using a box, rendering with openmapquest's and cyclemap style

	python3 bigtilemap.py -b-1.5978,46.3536,-0.9098,45.9411 -z11 -sopenmapquest.road,thunderforest.cyclemap

Public Transport near Edinburgh using a box, rendered with thunderforest transport

	python3 bigtilemap.py -b-3.4197,55.9024,-3.2468,55.9761 -z15 -sthunderforest.transport

Forbidden City (Beijing, China) using a box, rendered with Stamen's Watercolor map design

	python3 bigtilemap.py -b116.3727,39.9025,116.4019,39.9346 -z16 -sstamen.watercolor

Venizia using Nominatim, rendered with MapBox�s Pencil style

	python3 bigtilemap.py -fVenezia -z12 -smapbox.pencil

Aix Island (France) using Nominatim, rendered with all satellite view :

	python3 bigtilemap.py -f"Ile d'Aix" -z16 -s*satellite

Angkor Wat Temple (Cambodia), rendered with Pencil (from mapbox)

	python3 bigtilemap.py -nangkor -smapbox.pencil

Colorful Grand Prismatic Spring (USA), satellites :

	python3 bigtilemap.py -ncolorful

-- Notes ----------------------------------------------------------------------------------

bigtilemap/pmx support many Tile Map Servers (TMS) or slippy map, to have a detailed list (with licence and zoom available) :
	python3 bigtilemap.py -d

Support for many OSM data renderer and some experimental commercial servers (google, bing, yandex...)

bigtilemap/pmx respects mapnik tile usage policy : <http://wiki.openstreetmap.org/wiki/Tile_usage_policy>
meaning :
  - clearly display licence attribution : OdbL for data and CC-BY-SA for renderer 
      see : <http://www.openstreetmap.org/copyright>
  - valid User-Agent identifying application (kHTTP_User_Agent, see below)
  - cache Tile downloads locally (7 days recommended)
  - maximum of 2 download threads

To respect those recommendations, bigtilemap/pmx use a local cache and do not allow for request over 300 tiles per request.

Parameters :

Main parameters are defined into config.py file.

-- Warning ---------------------------------------------------------------------------------

Use it with respect to Tile Server usage policy : do not download large area at high zoom and do not use it too often.
Remember tile servers are not intend for local usage but for online browser usage.
Do not forget to clearly display licence on final map/usage :
	for osm : <http://www.openstreetmap.org/copyright>

Some TMS require using your own API Key (ie. MapBox, Lyrk, Here rendering).
For those services you have to get an API key and copy it into the configuration file : api_key.ini

ArcGIS render is not based on OSM and has a different licence : cc-by-sa-nc (add no commercial uses)

Google, Bing or Nokia may not be used for any none-personnal use, read carefully commercial licences, local upload is probably not allowed. Using mpx/bigmap with google often lead to be banned after some minutes.

-- Tile Servers Supported -------------------------------------------------------------------------

To get actual complete list of tile and server available : python3 bigtilemap.py -d
TMS are configured in servers.ini file.

Main providers (OSM data : free & open licence):

* OSM : default, fr, de, hot...
* Thunderforest : cyclemap, transport, landscape...
* Stamen : nice graphical rendering like watercolor, toner (with many overlay)
* Mapbox : (require an API key) many nice maps from OSM
* OpenTopoMap : nice topo map
* CartoDB : nice clean map with overlays
* OpenMapSurfer : general map (with 3D buildings from zoom level) and many overlay

Not OSM data but free & open licence (commercial restrictions) :

* ArcGis : street, topo, terrain, ocean : cc-by-sa-nc licence

Satellite :

* Bluemarble : NASA satellite assembly of 2004 cloud-free pictures (public domain)
* MapBox : source NASA, DigitalGlobe and USGC
* ArcGIS : source NASA, USGC
* Google : usage restricted see Google licence
* Bing : usage restricted see Microsoft licence

Special Data :

* OpenWeatherMap : meteo, but still experimental (server seem very slow)
* OpenPort : meteo at high zoom level
* Gibs (NASA) : time stamped data, experimental, usage restricted see NASA/GIBS licence. Display satelite images and scientific data once per day
 * used with --date option
* ITO : provide overlay with special data (electricity, water, railway...)

Not open licence (commercial services, may not works always fine)

* Google : usage restricted see Google licence
* Bing : usage restricted see Microsoft licence
* Nokia : usage restricted see Nokia licence
* Here : usage restricted see Nokia licence 'require an API key)'
* Yandex : experimental, usage restricted see Yandex licence

-- Search service ------------------------------------------------------------------------------

Search services provide through OpenStreetMap's Nominatim service : <http://wiki.openstreetmap.org/wiki/Nominatim>

Based on OSM data, can be used with bigmap (-s option) or bigmap_nominatim or pmx ; also provide reverse-search.

Detailed information about Nominatim : 
	<http://wiki.openstreetmap.org/wiki/Nominatim>
	<http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy>

Nominatim better work with request build from left to right using detail (left) and country (right).
Using comma improve performance (making query less complex).

A good example : "12 baker street, london, england"
Poor example (but works) : "baker street"
bad example : baker

-- Configuration --------------------------------------------------------------------------------

pmx/bigtilemap use configuration files (store in the source directory)

* servers.ini	describe TMS supported
* location.ini	describe some default location
* api_key.ini	describe api key for TMS requiring access key
* resource		directory with some pictures for pmx GUI

pmx/bigtilemap store user data in the default system user directory (home) :

* pmx.db		store user configuration (window size, default TMS, last search...) into a SQLite database
* cache			store cached Tile from TMS (see cache above)

-- End note -------------------------------------------------------------------------------------

Thanks to all OpenStreetMap contributors for the data, software and services provided
Thanks for Guido van Rossum for inventing Python and to the "Monty Python Flying Circus" to inspire him.

