# Python App to define waypoints on a map.

The App enables the user to select points on the map so to gather it's latitude and longitude values.

# How to run it

1. Clone the repository.
   
2. `cd` the src directory

3. Run a small local web server in the same directory as `map_view.html`.
```
python3 -m http.server 8000
```

4. Create a python environment 
```
python3 -m venv venv
```

5. Activate the environment
```
source venv/bin/activate
```

6. Install all the requirements
```
pip install -r requirements.txt
```

7. Insert your Google Maps API key
On the `map_view.html` file. Line 20
``` html
<!-- Google Maps JavaScript API -->
<!-- Insert your Google Maps Key Below -->
<script src="https://maps.googleapis.com/maps/api/js?key=GOOGLE_MAPS_KEY"></script>
```

8. On another terminal window, run the app and have fun
```
python3 map_point_selector.py 
```

# Working example
![Image](https://github.com/user-attachments/assets/103751cf-a7a7-40b3-bf99-d82dce872d82)
