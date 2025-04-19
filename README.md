# worldsheight
Generates height map of Earth section by given latitude/longitude (using open-elevation.com, so internet connection is required).

### Usage:
    ./worldsheight.py "start_latitude, start_longitude" "end_latitude, end_longitude" width_pixels save_path.png
For instance:

    ./worldsheight.py "49.0885, 37.4867" "48.9843, 37.6024" 4096 test.png
