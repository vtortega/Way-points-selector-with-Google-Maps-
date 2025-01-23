#!/usr/bin/env python3
import sys
import os
import socketserver
import http.server
import threading
import yaml

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QListWidget,
    QPushButton, QFileDialog
)
from PyQt5.QtCore import QUrl, QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

# Local http server

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

# JS -> Python Bridge

class Bridge(QObject):
    """
    Exposed to JavaScript as 'bridge'. 
    JavaScript calls: bridge.pointAdded(lat, lng, marker_id).
    """
    pointAddedSignal = pyqtSignal(float, float, int)

    @pyqtSlot(float, float, int)
    def pointAdded(self, lat, lng, marker_id):
        self.pointAddedSignal.emit(lat, lng, marker_id)

# Main Window

class MapPointSelector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Map Point Selector")
        self.resize(1200, 800)

        # We'll store points as (lat, lng, marker_id)
        self.points = []

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left: QWebEngineView
        self.webview = QWebEngineView()
        main_layout.addWidget(self.webview, stretch=2)

        # Right: list + buttons
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=1)

        self.listWidget = QListWidget()
        right_layout.addWidget(self.listWidget, stretch=1)

        # Clear All
        btn_clear_all = QPushButton("Clear All")
        btn_clear_all.clicked.connect(self.clearAll)
        right_layout.addWidget(btn_clear_all)

        # Save YAML
        btn_save = QPushButton("Save YAML")
        btn_save.clicked.connect(self.saveYaml)
        right_layout.addWidget(btn_save)

        # Setup QWebChannel
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.webview.page().setWebChannel(self.channel)

        # Connect Python side to JS signals
        self.bridge.pointAddedSignal.connect(self.onPointAdded)

        # Load HTML from local server
        url = f"http://127.0.0.1:{PORT}/map_view.html"
        self.webview.load(QUrl(url))

    @pyqtSlot(float, float, int)
    def onPointAdded(self, lat, lng, marker_id):
        """Called from JS when user clicks the map."""
        self.points.append((lat, lng, marker_id))
        self.listWidget.addItem(f"{lat:.6f}, {lng:.6f} [ID:{marker_id}]")

    def clearAll(self):
        """Remove all markers and points."""
        # Remove markers on the JS side
        for (lat, lng, marker_id) in self.points:
            script = f"removeMarker({marker_id});"
            self.webview.page().runJavaScript(script)

        # Clear our local storage and the list
        self.points.clear()
        self.listWidget.clear()

    def saveYaml(self):
        """Save points as a YAML for global_route_publisher."""
        if not self.points:
            return

        data = {"global_route": []}
        for (lat, lng, _) in self.points:
            data["global_route"].append({"lat": lat, "lon": lng})

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save YAML", "route.yaml", "YAML Files (*.yaml)"
        )
        if filename:
            with open(filename, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            print(f"Saved:", filename)


def main():
    # Start server in background
    server_thread = threading.Thread(target=start_local_server, daemon=True)
    server_thread.start()

    # Run Qt app
    app = QApplication(sys.argv)
    window = MapPointSelector()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
