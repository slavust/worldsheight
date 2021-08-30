#!/usr/bin/python3

import math
import numpy as np
from PIL import Image
import urllib.request
import json
import sys

def to_radians(degrees):
    return (degrees / 180.0) * math.pi

def to_degrees(radians):
    return (radians / math.pi)*180

# projecting latitude/longitude onto a tangent plane:
# https://www.mers.byu.edu/docs/reports/MERS9904.pdf

def earth_to_plane(plane_center_on_earth, point_on_earth):
    earth_flatness = 1.0 / 298.257
    r_a = 6378.1363
    earth_local_radius = (1.0 - earth_flatness * (math.sin(point_on_earth[0])**2))*r_a

    d_latitude = point_on_earth[0] - plane_center_on_earth[0]
    d_longitude = point_on_earth[1] - plane_center_on_earth[1]

    latitude_radius = earth_local_radius * math.cos(point_on_earth[0])
    a = earth_local_radius * math.sin(d_latitude)
    b = latitude_radius * (1.0 - math.cos(d_longitude))*math.sin(plane_center_on_earth[0])
    c = latitude_radius * math.sin(d_longitude)

    x = c
    y = a+b
    return (x, y)


def plane_to_earth(plane_center_on_earth, point_on_plane):
    earth_flatness = 1.0 / 298.257
    r_a = 6378.1363
    earth_local_radius = (1.0 - earth_flatness * (math.sin(point_on_plane[0])**2))*r_a

    latitude_radius = earth_local_radius * math.cos(plane_center_on_earth[0])
    d_longitude = math.asin(point_on_plane[0]/latitude_radius)
    
    d_latitude = math.asin((point_on_plane[1] - (1.0 - math.cos(d_longitude))*math.sin(plane_center_on_earth[0])*latitude_radius) / earth_local_radius)

    return plane_center_on_earth + np.array([d_latitude, d_longitude])


def request_heights(mapping):
    all_locations = []
    num_locations = 0
    for x in range(mapping.shape[0]):
        for y in range(mapping.shape[1]):
            loc = {"latitude":to_degrees(mapping[x, y, 0]), "longitude": to_degrees(mapping[x, y, 1])}
            all_locations.append(loc)
            num_locations += 1

    if len(all_locations) == 0:
        return None

    elevations_list = []
    num_locations_at_once = 1000
    cur_loc = 0
    for cur_loc in range(0, num_locations, num_locations_at_once):
        block_size = min(int(num_locations_at_once), int(num_locations) - int(cur_loc))
        block = all_locations[cur_loc : cur_loc + block_size]

        location = {"locations": block}
        json_data = json.dumps(location, skipkeys=int).encode('utf8')

        url = "https://api.open-elevation.com/api/v1/lookup"
        request = urllib.request.Request(url, json_data, 
        headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
        fp=urllib.request.urlopen(request)

        res_byte=fp.read()
        res_str=res_byte.decode("utf8")
        js_str=json.loads(res_str)
        fp.close()
        elevations_list.extend([float(res['elevation']) for res in js_str['results']])

    elevations = np.zeros(mapping.shape[:2])
    for x in range(mapping.shape[0]):
        for y in range(mapping.shape[1]):
            indx = x*mapping.shape[1]+y
            elevations[x, y] = elevations_list[indx]
    
    return elevations

def normalize_elevations(elevations):
    minimum = np.min(elevations)
    maximum = np.max(elevations)
    elevations = (elevations - minimum) / (maximum - minimum)
    return minimum, maximum

def main(point_on_earth_min, point_on_earth_max, heightmap_width_pixels, heightmap_save_path):
    plane_center_on_earth = (point_on_earth_min + point_on_earth_max) / 2.0
    
    plane_bottom_left = earth_to_plane(plane_center_on_earth, point_on_earth_min)
    plane_top_right = earth_to_plane(plane_center_on_earth, point_on_earth_max)

    elevation_data_meters_per_pixel = 250
    width = plane_top_right[0] - plane_bottom_left[0]
    step = width / heightmap_width_pixels
    heightmap_width_pixels_corrected = heightmap_width_pixels
    step_corrected = step
    if step*1000 < elevation_data_meters_per_pixel:
        step_corrected = elevation_data_meters_per_pixel / 1000.0
        heightmap_width_pixels_corrected = round(width / step_corrected)

    height = plane_top_right[1]-plane_bottom_left[1]
    height_corrected = round(height / step_corrected) * step_corrected
    heightmap_height_pixels = int(height_corrected / step_corrected)
    mapping = np.zeros((heightmap_width_pixels_corrected, heightmap_height_pixels, 2))
    for i in range(heightmap_width_pixels_corrected):
        for j in range(heightmap_height_pixels):
            x = plane_bottom_left[0] + i*step_corrected
            y = plane_bottom_left[1] + j*step_corrected
            mapping[i, j] = plane_to_earth(plane_center_on_earth, np.array([x, y]))
    
    heights = request_heights(mapping)
    del mapping
    minimum, maximum = normalize_elevations(heights)

    im = Image.fromarray(heights)
    im = im.convert('L')
    im = im.transpose(Image.ROTATE_90)
    if heightmap_width_pixels_corrected != heightmap_width_pixels:
        new_height = round(heightmap_height_pixels * heightmap_width_pixels / heightmap_width_pixels_corrected)
        im = im.resize((heightmap_width_pixels, new_height), resample=Image.LANCZOS)

    im.save(heightmap_save_path)
    print('Meters per pixel: {}'.format(step * 1000))
    print('Min meters above sea level: {}'.format(minimum))
    print('Max meters above sea level: {}'.format(maximum))


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print('Usage: ./worldsheight.py "start_latitude, start_longitude" "end_latitude, end_longitude" texture_width_pixels texture_save_path.png')
        print('Example: ./worldsheight.py "49.0885, 37.4867" "48.9843, 37.6024" 4096 test.png')
        exit(0)

    start_pt_str = sys.argv[1]
    end_pt_str = sys.argv[2]
    tex_width_pixels = int(sys.argv[3])
    save_path = sys.argv[4]

    start_pt_la, start_pt_lo = [float(s) for s in start_pt_str.split(", ")]
    end_pt_la, end_pt_lo = [float(s) for s in end_pt_str.split(", ")]

    minimum = np.array([to_radians(min(start_pt_la, end_pt_la)),to_radians(min(start_pt_lo, end_pt_lo))])
    maximum = np.array([to_radians(max(start_pt_la, end_pt_la)),to_radians(max(start_pt_lo, end_pt_lo))])
    main(minimum, maximum, tex_width_pixels, save_path)
