#!/usr/bin/env python3
import sys
import os
import socketserver
import http.server
import threading
import yaml

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QPushButton, QFileDialog, QComboBox, QTextEdit,
    QDialog, QDialogButtonBox, QLabel
)
from PyQt5.QtCore import QUrl, QObject, pyqtSlot, pyqtSignal, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

# ---------- Local HTTP Server ----------
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class CustomRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files from BASE_DIR on localhost:PORT."""
    def translate_path(self, path):
        new_path = http.server.SimpleHTTPRequestHandler.translate_path(self, path)
        rel_path = os.path.relpath(new_path, os.getcwd())
        return os.path.join(BASE_DIR, rel_path)

def start_local_server():
    """Starts an HTTP server in a background thread."""
    os.chdir(BASE_DIR)
    with socketserver.TCPServer(("", PORT), CustomRequestHandler) as httpd:
        print(f"Serving at http://127.0.0.1:{PORT}")
        httpd.serve_forever()

# ---------- JS <-> Python Bridge ----------
class Bridge(QObject):
    # Now sending four parameters: lat, lng, marker_id, and route_id.
    pointAddedSignal = pyqtSignal(float, float, int, int)
    markerMovedSignal = pyqtSignal(float, float, int, int)

    @pyqtSlot(float, float, int, int)
    def pointAdded(self, lat, lng, marker_id, route_id):
        self.pointAddedSignal.emit(lat, lng, marker_id, route_id)

    @pyqtSlot(float, float, int, int)
    def markerMoved(self, lat, lng, marker_id, route_id):
        self.markerMovedSignal.emit(lat, lng, marker_id, route_id)

# ---------- Dialog for pasting YAML text ----------
class YamlTextDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paste YAML Content")
        self.resize(400, 300)
        layout = QVBoxLayout(self)
        self.label = QLabel("Paste your YAML content below:")
        layout.addWidget(self.label)
        self.textEdit = QTextEdit(self)
        layout.addWidget(self.textEdit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getText(self):
        return self.textEdit.toPlainText()

# ---------- Main Window ----------
class MapPointSelector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Map Point Selector")
        self.resize(1200, 800)
        self.setAcceptDrops(True)  # Enable drag-and-drop

        # Data model: routes dictionary.
        # Each route is a dict with keys: id, color, and points (a list of (marker_id, lat, lng)).
        self.routes = {}
        self.currentRouteId = 0
        self.nextRouteId = 1  # Used for creating new routes
        self.colors = ["red", "blue", "green", "orange", "purple", "cyan", "magenta"]

        # Create a default route (ID 0)
        self.routes[self.currentRouteId] = {'id': self.currentRouteId, 'color': self.colors[0], 'points': []}

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left: QWebEngineView for the map.
        self.webview = QWebEngineView()
        main_layout.addWidget(self.webview, stretch=2)

        # Right: UI controls and list of points.
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=1)

        # Combo box to select the current route.
        self.routeComboBox = QComboBox()
        self.routeComboBox.addItem(f"Route {self.currentRouteId} ({self.routes[self.currentRouteId]['color']})", self.currentRouteId)
        self.routeComboBox.currentIndexChanged.connect(self.changeRoute)
        right_layout.addWidget(self.routeComboBox)

        # Button to add a new route.
        btn_new_route = QPushButton("New Route")
        btn_new_route.clicked.connect(self.newRoute)
        right_layout.addWidget(btn_new_route)

        # Button to clear only the current route.
        btn_clear_current_route = QPushButton("Clear Current Route")
        btn_clear_current_route.clicked.connect(self.clearCurrentRoute)
        right_layout.addWidget(btn_clear_current_route)

        # Button to clear all routes.
        btn_clear_all = QPushButton("Clear All")
        btn_clear_all.clicked.connect(self.clearAll)
        right_layout.addWidget(btn_clear_all)

        # List widget to display points.
        self.listWidget = QListWidget()
        right_layout.addWidget(self.listWidget, stretch=1)

        # Button to save routes as a YAML file.
        btn_save = QPushButton("Save YAML")
        btn_save.clicked.connect(self.saveYaml)
        right_layout.addWidget(btn_save)

        # Button to load YAML from pasted text.
        btn_load_text = QPushButton("Load YAML from Text")
        btn_load_text.clicked.connect(self.loadYamlFromText)
        right_layout.addWidget(btn_load_text)

        # Button to load YAML from a file.
        btn_load_file = QPushButton("Load YAML from File")
        btn_load_file.clicked.connect(self.loadYamlFromFile)
        right_layout.addWidget(btn_load_file)

        # Button to toggle the display of POI (labels for restaurants, universities, etc.)
        btn_toggle_poi = QPushButton("Toggle POI")
        btn_toggle_poi.clicked.connect(self.togglePOI)
        right_layout.addWidget(btn_toggle_poi)

        # Setup QWebChannel and the JS-Python bridge.
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.webview.page().setWebChannel(self.channel)

        self.bridge.pointAddedSignal.connect(self.onPointAdded)
        self.bridge.markerMovedSignal.connect(self.onMarkerMoved)

        # Load the HTML page from the local server.
        url = QUrl(f"http://127.0.0.1:{PORT}/map_view.html")
        self.webview.load(url)

        # Once the page loads, tell the JS side the current route and create the default route.
        self.webview.page().runJavaScript(f"setCurrentRoute({self.currentRouteId});")
        self.webview.page().runJavaScript(f"addRoute({self.currentRouteId}, '{self.routes[self.currentRouteId]['color']}');")

    # ---------- Drag and Drop support for YAML files ----------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        # Process the first file that ends with .yaml or .yml.
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".yaml", ".yml")):
                with open(file_path, 'r') as f:
                    content = f.read()
                    self.loadYamlContent(content)
                break

    def loadYamlFromText(self):
        dialog = YamlTextDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            text = dialog.getText()
            self.loadYamlContent(text)

    def loadYamlFromFile(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open YAML File", "", "YAML Files (*.yaml *.yml)")
        if filename:
            with open(filename, 'r') as f:
                content = f.read()
            self.loadYamlContent(content)

    def loadYamlContent(self, content):
        try:
            data = yaml.safe_load(content)
        except Exception as e:
            print("Failed to parse YAML:", e)
            return

        # Check if the YAML contains multiple routes or a single route.
        if "routes" in data:
            routes = data["routes"]
            for route in routes:
                self.addRouteFromData(route)
        elif "global_route" in data:
            # If only a single route was saved (using the older format), wrap it as one route.
            route_data = {
                "id": self.nextRouteId,
                "color": self.colors[self.nextRouteId % len(self.colors)],
                "points": data["global_route"]
            }
            self.addRouteFromData(route_data)
        else:
            print("Invalid YAML format")

    def addRouteFromData(self, route_data):
        # Create a new route using our nextRouteId (ignoring any route id in the file).
        route_id = self.nextRouteId
        self.nextRouteId += 1
        color = route_data.get("color", self.colors[route_id % len(self.colors)])
        points = route_data.get("points", route_data.get("global_route", []))
        # Store the new route in our data model.
        self.routes[route_id] = {'id': route_id, 'color': color, 'points': []}
        # Add it to the route selection combo box.
        self.routeComboBox.addItem(f"Route {route_id} ({color})", route_id)
        # Instruct the JS side to create the route.
        self.webview.page().runJavaScript(f"addRoute({route_id}, '{color}');")
        # Add each point from the YAML file.
        for point in points:
            lat = point.get("lat")
            # Allow either "lon" or "lng"
            lng = point.get("lon") or point.get("lng")
            if lat is not None and lng is not None:
                marker_id = len(self.routes[route_id]['points'])
                self.routes[route_id]['points'].append((marker_id, lat, lng))
                self.webview.page().runJavaScript(f"addMarkerToRoute({route_id}, {marker_id}, {lat}, {lng});")
                self.listWidget.addItem(f"Route {route_id}: {lat:.6f}, {lng:.6f} [ID:{marker_id}]")

    def newRoute(self):
        # Create a new route.
        route_id = self.nextRouteId
        self.nextRouteId += 1
        color = self.colors[route_id % len(self.colors)]
        self.routes[route_id] = {'id': route_id, 'color': color, 'points': []}
        self.routeComboBox.addItem(f"Route {route_id} ({color})", route_id)
        # Switch to the new route.
        index = self.routeComboBox.count() - 1
        self.routeComboBox.setCurrentIndex(index)
        self.webview.page().runJavaScript(f"addRoute({route_id}, '{color}');")
        self.webview.page().runJavaScript(f"setCurrentRoute({route_id});")

    def changeRoute(self, index):
        # Change the active route.
        route_id = self.routeComboBox.itemData(index)
        if route_id is not None:
            self.currentRouteId = route_id
            self.webview.page().runJavaScript(f"setCurrentRoute({route_id});")

    @pyqtSlot(float, float, int, int)
    def onPointAdded(self, lat, lng, marker_id, route_id):
        # Called when JS notifies us of a new marker.
        if route_id not in self.routes:
            route_id = self.currentRouteId
        self.routes[route_id]['points'].append((marker_id, lat, lng))
        self.listWidget.addItem(f"Route {route_id}: {lat:.6f}, {lng:.6f} [ID:{marker_id}]")

    @pyqtSlot(float, float, int, int)
    def onMarkerMoved(self, lat, lng, marker_id, route_id):
        # Called when a marker is moved (dragged) in JS.
        if route_id in self.routes:
            points = self.routes[route_id]['points']
            for i, (mid, old_lat, old_lng) in enumerate(points):
                if mid == marker_id:
                    points[i] = (mid, lat, lng)
                    self.listWidget.addItem(f"Route {route_id}: Marker {marker_id} moved to {lat:.6f}, {lng:.6f}")
                    break

    def clearCurrentRoute(self):
        """Remove only the markers and polyline for the current route and clear its data."""
        # Instruct JS to clear markers for current route.
        self.webview.page().runJavaScript(f"clearCurrentRoute({self.currentRouteId});")
        # Clear the data for current route.
        if self.currentRouteId in self.routes:
            self.routes[self.currentRouteId]['points'].clear()
        # Remove listWidget items corresponding to current route.
        for i in range(self.listWidget.count()-1, -1, -1):
            item = self.listWidget.item(i)
            if item.text().startswith(f"Route {self.currentRouteId}:"):
                self.listWidget.takeItem(i)

    def clearAll(self):
        """Remove all routes (markers, polylines) from the JS side and reset the data model."""
        # Tell JS to clear everything.
        self.webview.page().runJavaScript("clearAllRoutes();")
        # Clear local data.
        self.routes.clear()
        self.listWidget.clear()
        self.routeComboBox.clear()
        # Reinitialize with a default route (ID 0).
        self.currentRouteId = 0
        self.nextRouteId = 1
        default_color = self.colors[0]
        self.routes[self.currentRouteId] = {'id': self.currentRouteId, 'color': default_color, 'points': []}
        self.routeComboBox.addItem(f"Route {self.currentRouteId} ({default_color})", self.currentRouteId)
        # Instruct JS to add default route.
        self.webview.page().runJavaScript(f"addRoute({self.currentRouteId}, '{default_color}');")
        self.webview.page().runJavaScript(f"setCurrentRoute({self.currentRouteId});")

    def saveYaml(self):
        """Save all routes to a YAML file."""
        if not self.routes:
            return

        data = {"routes": []}
        for route_id, route in self.routes.items():
            points_list = [{"lat": lat, "lon": lng} for (marker_id, lat, lng) in route['points']]
            data["routes"].append({"id": route_id, "color": route['color'], "points": points_list})
        filename, _ = QFileDialog.getSaveFileName(self, "Save YAML", "routes.yaml", "YAML Files (*.yaml)")
        if filename:
            with open(filename, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            print("Saved:", filename)

    def togglePOI(self):
        """Toggle the display of POI labels on the map."""
        self.webview.page().runJavaScript("togglePOI();")

def main():
    # Start the local HTTP server in a background thread.
    server_thread = threading.Thread(target=start_local_server, daemon=True)
    server_thread.start()

    # Start the Qt application.
    app = QApplication(sys.argv)
    window = MapPointSelector()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
