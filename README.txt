bigmap.py
-------------
New-BSD Licence, (c) 2010-2013, Pierre-Alain Dorange
-------------
Download tiles from a Tile Server (asynchronous) and assemble tiles into a big Map
Assemble tiles with PIL library (seperate install)

bigmap main purpose is to help users creating big image from OSM map data to print (very) large maps
read carefully licences and notes before using, not all maps have same licence and usage policy

usage
-----
python bigmap.py [parameters]
	-h (--help)		: get help
	-d (--display)  : display list of supported servers
	-l (--location) : define location latitude,longitude (-l45.6945,-0.3304)
	-z (--zoom)		: define zoom level (-z14)
	-t (--tile)		: define nb tile width and height to assemble (-w5,5)
	-s (--server)	: define tile server, default is mapnik (-sstamen_watercolor)
	-c (--cache)	: override local cache
	
To define those parameters, the easy method is to use www.openstreetmap.org, drag the map and zoom according to what you want
Click on "permanent link" (bottom-right) then the URL display coordinates and zoom, just re-use those value :
	ie : http://www.openstreetmap.org/?lat=45.7066&lon=-0.3296&zoom=14&layers=M
		lat is latitude
		lon is longitude
		zoom is the zoom level
		layers is the rendered tiles used
	ie : python bigmap.py -l45.7066,-0.3296 -t5,5 -z 14
	
To define nb tiles width and height (-t), just remember a tile is 256x256 pixels

notes
-----
	
Tile Servers support many tile render (or slippy map), to have a detailed list :
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

Licences
--------

Source code : 
	New-BSD Licence, (c) 2010-2013, Pierre-Alain Dorange
	
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
CloudMade tiles (render from OSM data) : CC-BY-SA : cloudmade_standard, cloudmade_fineline, cloudmade_fresh, cloudmade_tourism, cloudmade_1155
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

ArcGIS/ESRI tiles (ArcGIS) : CC-BY-SA-NC : arcgis_topo, arcgis_imagery, arcgis_terrain
	<http://www.esri.com/data/free-data/index.html>

BlueMarble : Public Domain, satelite pictures retouched produce by NASA
	<http://visibleearth.nasa.gov/view.php?id=57723>
MapBox Landsat : copyright MapBox/Landsat
Google (road, aerial) : copyright Google
Bing (road, aerial) : copyright Miscrosoft

History
-------
see bigmap.py header for a version history
