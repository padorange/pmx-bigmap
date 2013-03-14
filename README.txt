bigmap.py
-------------------------------------------------------
New-BSD Licence, (c) 2010-2013, Pierre-Alain Dorange
http://www.leretourdelautruche.com/pmwiki/index.php/Autruche/BigMap
-------------------------------------------------------
Download tiles from a Tile Server (asynchronous) and assemble tiles into a big Map
Assemble tiles with PIL library (separate install)

bigmap main purpose is to help users creating big image from OSM map data to print (very) large maps.
read carefully licences and notes before using, not all maps have same licence and usage policy

usage
-----
python bigmap.py [parameters]
	-h (--help)	: get help
	-d (--display)  : display list of supported servers
	-b (--box)	: define bounding box (longitude,latitude,longitude,latitude) (-b()
	-z (--zoom)	: define zoom level (-z14)
	-s (--server)	: define tile server, default is mapnik (-sstamen_watercolor)
	-t (--tile)	: define nb tile width and height to assemble (-w5,5)
	-l (--location) : define location longitude,latitude (-l-0.3304,45.6945)
	-c (--cache)	: override local cache
Two method can be used to define the map area :
	* classic bound box (corner of a square express in latitude, longitude) + a zoom level : -b -z
	* a center (latitude, longitude) + a nb-tile size +a zoom level : -l -t -z
	
To define those parameters, the easy method is to use www.openstreetmap.org, drag the map and zoom according to what you want
Click on "export" (up bar) adjust your view and get the 4 coordinates defining the bounding box :
	ie : 	up-left corner : -0.3797,45.7219
		down-right corner : -0.2784,45.648
		choose a detail-zoom level (16 to 18 par street details, 12-15 for region detail, 8-10 for country detail)
	ie : python bigmap.py -b-0.3797,45.7219,-0.2784,45.648 -z16
	
Alternavely you can use a center location and choose a nb-tile width and height around (buggy)
	ie : python bigmap.py -l-0.3797,45.7219 -t5,5 -z16

notes
-----
	
Tile Servers support many tile render (or slippy map), to have a detailed list (with licence and zoom available :
	python bigmap.py -d
	
	Support OSM data renderer +some experimental commercial servers (google, bing, landsat...)

BigMap respects mapnik tile usage policy : <http://wiki.openstreetmap.org/wiki/Tile_usage_policy>
  - clearly display licence attribution : CC-BY-SA <http://www.openstreetmap.org/copyright>
  - valid User-Agent identifying application (kHTTP_User_Agent, see below)
  - cache Tile downloads locally
  - maximum of 2 download threads
  
Warning : 
	Use it with respect to OSM usage policy : do not download large area at high zoom and donot use it too often
		remember OSM tile server are not intend for local usage but for online browser usage
	Do not forget to clearly display licence on final product : <http://www.openstreetmap.org/copyright>
	CloudMade render require using your own API Key (just login to CloudMade and copy the API Key in the source code)
	ArcGIS render is not based on OSM and has a different licence : cc-by-sa-nc (add no commercial uses)
	Google, Bing or Landsat may not be used, read carefully commercial licences, local upload is probably not allowed

Asynchronous Threads informations : 
	http://linuxgazette.net/107/pai.html
	http://effbot.org/zone/thread-synchronization.htm
	http://www.ibm.com/developerworks/aix/library/au-threadingpython/
	http://www.drdobbs.com/web-development/206103078;jsessionid=AYMZ4H2P3PWGXQE1GHPSKH4ATMY32JVN?pgno=1
	
Cache :
	bigmap.py use a local cache to store individual tiles, is you need to refrech local data, simply trash to cache folder
	-c option reload tiles
	Cache folder can rapidly became big and occupy lot of space on your hard-drive

Examples
--------
French atlantic coast near "La Rochelle" with openstreetmap, default rendering (mapnik)
	python bigmap.py -b-1.741,46.434,-0.478,45.652 -z10 -sopenmapquest
Public Transport near Edinburgh, rendered with transport
	python bigmap.py -b-3.4197,55.9024,-3.2468,55.9761 -z14 -stransport
Forbidden City (Beijing), rendered with Stamen's Watercolor
	python bigmap.py -b116.3727,39.9025,116.4019,39.9346 -z16 -sstamen_watercolor
Venise, rendered with acetate (Stamen & ESRI)
	python bigmap.py -b12.32203,45.4249,12.34205,45.43717 -z15 -s

Map Licences
------------

* OSM Based Maps 

OpenStreetMap (OSM) data : ODbL, (c) openstreetmap.org and contributors
	<http://www.openstreetmap.org/>
Mapnik tiles (OSM default style) : CC-BY-SA
	<http://www.openstreetmap.org/copyright>
CycleMap and Transport tiles : CC-BY-SA, created by Andy Allan
	<http://www.opencyclemap.org/>
OpenMapQuest and OpenAerial tiles: CC-BY-SA, created by MapQuest
	<http://open.mapquest.com/>
Stamen design tiles: CC-BY : stamen_watercolor, stamen_toner
	<http://stamen.com/>
CloudMade tiles (render from OSM data) : CC-BY-SA : cloudmade_standard, cloudmade_fineline, cloudmade_fresh, cloudmade_thin
	cloudmade require an API Key : <http://account.cloudmade.com/user>
	<http://cloudmade.com/>
Hikebike : CC-BY-SA by Colin Marquardt
	<http://hikebikemap.de/>
OPVNKarte : CC-BY-SA by Memomaps
	<http://www.öpnvkarte.de/>
Acetate (roads, background)
	<http://blog.geoiq.com/2011/01/19/announcing-acetate-better-thematic-mapping/>
PisteMap
	<http://openpistemap.org/>
PisteMap Landshaded, from NASA SRTM
	<http://openpistemap.org/>

* Other Free maps

ArcGIS/ESRI tiles (ArcGIS) : CC-BY-SA-NC : arcgis_topo, arcgis_imagery, arcgis_terrain
	<http://www.esri.com/data/free-data/index.html>

* Public Domain

BlueMarble : Public Domain, satelite pictures retouched produce by NASA
	<http://visibleearth.nasa.gov/view.php?id=57723>

Commercial Maps (read carefully licence, most won't allow bigmap.py usage)

MapBox Landsat : copyright MapBox/Landsat
Google (road, aerial) : copyright Google
Bing (road, aerial) : copyright Miscrosoft
NokiaMaps (road, grey, satellite and terrain) : copyright Nokia

History
-------
see bigmap.py header for a version history
