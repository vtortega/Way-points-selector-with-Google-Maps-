# Python App to define waypoints on a map.

The App enables the user to select points on the map so to gather it's latitude and longitude values.

# How to run it

1. Clone the repository.
   
2. `cd` the src directory

3. Create a python environment 
```
python 3 -m venv venv
```

4. Activate the environment
```
source venv/bin/activate
```

4. Install all the requirements
```
pip install -r requirements.txt
```

5. Insert your Google Maps API key
On the `map_view.html` file. Line 20
``` html
<!-- Google Maps JavaScript API -->
<!-- Insert your Google Maps Key Below -->
<script src="https://maps.googleapis.com/maps/api/js?key=GOOGLE_MAPS_KEY"></script>
```

7. Run the server to the correct port
```
python3 -m http.server 8000
```

7. On another terminal window, run the app and have fun
```
python3 map_point_selector.py 
```
