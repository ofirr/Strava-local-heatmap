"""
Remi Salmon
salmon.remi@gmail.com

November 17, 2017

References:
https://support.strava.com/hc/en-us/articles/216918437-Exporting-your-Data-and-Bulk-Export

http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
http://wiki.openstreetmap.org/wiki/Tile_servers

    http://matplotlib.org/examples/color/colormaps_reference.html

http://scikit-image.org/

https://www.findlatitudeandlongitude.com/
"""

#%% librairies
import sys
import glob
import time
import re
import requests
import math
import matplotlib
import numpy
import skimage.color
import skimage.filters
import skimage.io

#%% functions

# return OSM x,y tile ID from lat,lon in degrees
def deg2num(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 2.0 ** zoom
  xtile = int((lon_deg + 180.0) / 360.0 * n)
  ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
  return(xtile, ytile)

# return x,y coordinates in tile from lat,lon in degrees
def deg2xy(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = (lon_deg + 180.0) / 360.0 * n
    x = x-math.floor(x)
    y = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    y = y-math.floor(y)
    return(x, y)

# download image
def downloadtile(url, filename):
    req = requests.get(url)
    with open(filename, 'wb') as file:
        for chunk in req.iter_content(chunk_size = 256):
            file.write(chunk)
            file.flush()
    time.sleep(0.1)
    return

#%% parameters
# latitude, longitude bounding box
#min_lat = 29.5
#max_lat = 30.2
#min_lon = -96.0
#max_lon = -95.0

zoom = 13 # OSM zoom level
tile_size = [256, 256] # OSM default

i_factor = 3.0 # background map intensity reduction factor: lower i_factor == background map less visible

k_data = 1.0/6.0 # logistic function parameter: lower k_data == more trackpoints needed to show a high density on the heatmap

sigma_pixels = 1.5 # Gaussian kernel sigma: half bandwith, in pixels

colormap_style = 'jet' # heatmap color map, from matplotlib

#%% main

# find gpx file
gpx_files = glob.glob('gpx/*.gpx')

# initialize list
lat_lon_data = []

# read GPX files
for i in range(len(gpx_files)):
    print('reading GPX file '+str(i+1)+'/'+str(len(gpx_files))+'...')
        
    with open(gpx_files[i]) as file:
        for line in file:
            # get trackpoints latitude, longitude
            if '<trkpt' in line:
                tmp = re.findall('-?\d*\.?\d+', line)
                
                lat = float(tmp[0])
                lon = float(tmp[1])
                
                lat_lon_data.append([lat, lon])

# convert to NumPy array
lat_lon_data = numpy.array(lat_lon_data)

print('processing GPX data...')

# find corresponding OSM tiles IDs x,y
xy_tiles = numpy.zeros(numpy.shape(lat_lon_data), dtype = int)

for i in range(len(xy_tiles)):
    xy_tiles[i, :] = deg2num(lat_lon_data[i, 0], lat_lon_data[i, 1], zoom)

# find bounding OSM x,y tiles ID
x_tile_min = min(xy_tiles[:, 0])
x_tile_max = max(xy_tiles[:, 0])
y_tile_min = min(xy_tiles[:, 1])
y_tile_max = max(xy_tiles[:, 1])

# check area size
tile_count = (x_tile_max-x_tile_min+1)*(y_tile_max-y_tile_min+1)
if tile_count > 300:
    print('area too large, reduce zoom or check GPX files\ntile_count = '+str(tile_count))
    sys.exit('ERROR_tile_count')

# download tiles
i = 0
for x in range(x_tile_min, x_tile_max+1):
    for y in range(y_tile_min, y_tile_max+1):
        tile_url = 'https://maps.wikimedia.org/osm-intl/'+str(zoom)+'/'+str(x)+'/'+str(y)+'.png'
        tile_filename = 'tiles/tile_'+str(zoom)+'_'+str(x)+'_'+str(y)+'.png'
        
        if len(glob.glob(tile_filename)) == 0:
            i = i+1
            print('downloading tile '+str(i)+'/'+str(tile_count)+'...')
            
            downloadtile(tile_url, tile_filename)

# create supertile
supertile_size = [math.floor(y_tile_max-y_tile_min+1)*tile_size[0], math.floor((x_tile_max-x_tile_min+1)*tile_size[1]), 3]

supertile = numpy.zeros(supertile_size)
supertile_gray = numpy.zeros(supertile_size[0:2])

# read tiles and fill supertile
for x in range(x_tile_min, x_tile_max+1):
    for y in range(y_tile_min, y_tile_max+1):
        tile_filename = 'tiles/tile_'+str(zoom)+'_'+str(x)+'_'+str(y)+'.png'
        tile = skimage.io.imread(tile_filename) # uint8 data type
        
        tile = skimage.color.rgb2gray(tile) # OSM tiles have either 1 or 3 channels..., reduce to 1 by default
        
        i = y-y_tile_min
        j = x-x_tile_min
        supertile_gray[i*tile_size[0]:i*tile_size[0]+tile_size[0], j*tile_size[1]:j*tile_size[1]+tile_size[1]] = skimage.img_as_float(tile)
        
# convert supertile to 3 channels image
supertile = skimage.color.gray2rgb(supertile_gray)

# invert supertile colors
supertile = 1-supertile

# reduce OSM map intensity
supertile  = supertile/i_factor

# fill trackpoints data
data = numpy.zeros(supertile_size[0:2])

for k in range(len(lat_lon_data)):
    (x, y) = deg2xy(lat_lon_data[k, 0], lat_lon_data[k, 1], zoom)
    
    i = math.floor(y*tile_size[0])
    j = math.floor(x*tile_size[1])
    
    i = i+(xy_tiles[k, 1]-y_tile_min)*tile_size[0]
    j = j+(xy_tiles[k, 0]-x_tile_min)*tile_size[1]
    
    data[i-1:i+1, j-1:j+1] = data[i-1:i+1, j-1:j+1] + 1 # GPX trackpoint is 3x3 pixels

# transform trackpoints density with logistic function + normalization
data = 1.0/(1.0+numpy.exp(-k_data*(data-0))) # find more robust estimattion of k_data
data = (data-data.min())/(data.max()-data.min())

# kernel density estimation: convolution with Gaussian kernel + normalization
data = skimage.filters.gaussian(data, sigma_pixels)
data = (data-data.min())/(data.max()-data.min())

# colorize data
cmap = matplotlib.pyplot.get_cmap(colormap_style)
data_color = cmap(data)
data_color = data_color[:, :, 0:3] # remove alpha channel

# create color overlay
supertile_overlay = numpy.zeros(supertile_size)

# fill color overlay
for c in range(3):    
    supertile_overlay[:, :, c] = (1-data_color[:, :, c])*supertile[:, :, c]+data_color[:, :, c]

# crop values out of range [0,1]
supertile_overlay = numpy.minimum.reduce([supertile_overlay, numpy.ones(supertile_size)])
supertile_overlay = numpy.maximum.reduce([supertile_overlay, numpy.zeros(supertile_size)])

# save image
print('writing heatmap.png...')
skimage.io.imsave('heatmap.png', supertile_overlay)
