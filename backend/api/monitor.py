from http.server import BaseHTTPRequestHandler
import os
import json
import psycopg2

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Trigger a check for a specific route or all active routes
        # For MVP, this might just return the status of a route for the app to display
        # Or it could trigger a push notification (if we had APNs)
        
        # Let's make this an endpoint that checks a route's status and returns "Alert" or "OK"
        
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length)
        data = json.loads(body)
        
        route_id = data.get("route_id")
        if not route_id:
            self.send_error(400, "Missing route_id")
            return

        db_url = os.environ.get("DATABASE_URL")
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # Get route details
            cur.execute("SELECT start_station_id, end_station_id FROM routes WHERE route_id = %s", (route_id,))
            route = cur.fetchone()
            if not route:
                self.send_error(404, "Route not found")
                return
                
            start_id, end_id = route
            
            # Check status
            # We need the LATEST status for start and end stations
            query = """
                SELECT station_id, num_bikes_available, num_docks_available 
                FROM station_status 
                WHERE station_id IN (%s, %s)
                ORDER BY time DESC
            """
            # This query is slightly flawed as it gets latest of ALL, we need latest PER station.
            # Correct:
            query = """
                SELECT DISTINCT ON (station_id) station_id, num_bikes_available, num_docks_available
                FROM station_status
                WHERE station_id IN (%s, %s)
                ORDER BY station_id, time DESC
            """
            
            cur.execute(query, (start_id, end_id))
            rows = cur.fetchall()
            
            status = {}
            for r in rows:
                status[r[0]] = {"bikes": r[1], "docks": r[2]}
            
            # Logic for alert
            # Simple heuristic: < 2 bikes at start, or < 2 docks at end
            alert = False
            message = []
            
            start_status = status.get(start_id)
            end_status = status.get(end_id)
            
            if start_status and start_status["bikes"] < 2:
                alert = True
                message.append(f"Low bikes at start ({start_status['bikes']} avail)")
                
            if end_status and end_status["docks"] < 2:
                alert = True
                message.append(f"Low docks at dest ({end_status['docks']} avail)")
                
            self.send_json({
                "alert": alert,
                "message": "; ".join(message) if message else "Good to go",
                "data": status
            })
            
            cur.close()
            conn.close()
            
        except Exception as e:
            self.send_error(500, str(e))

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error(self, status, message):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
