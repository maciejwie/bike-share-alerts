from http.server import BaseHTTPRequestHandler
import os
import json
import psycopg2
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            self.send_error(500, "DATABASE_URL not set")
            return

        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()

            if method == "GET":
                # Parse query params for user_id
                query = urlparse(self.path).query
                params = parse_qs(query)
                user_id = params.get("user_id", [None])[0]

                if not user_id:
                    self.send_error(400, "Missing user_id")
                    return

                cur.execute("SELECT route_id, name, start_station_id, end_station_id, target_arrival_time, alert_lead_time_minutes, days_of_week, is_active FROM routes WHERE user_id = %s", (user_id,))
                rows = cur.fetchall()
                
                routes = []
                for row in rows:
                    routes.append({
                        "id": row[0],
                        "name": row[1],
                        "start_station": row[2],
                        "end_station": row[3],
                        "arrival_time": str(row[4]) if row[4] else None,
                        "lead_time": row[5],
                        "days": row[6],
                        "active": row[7]
                    })
                
                self.send_json({"routes": routes})

            elif method == "POST":
                length = int(self.headers.get('content-length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                
                # Basic validation
                required = ["user_id", "name", "start_station_id", "end_station_id"]
                if not all(k in data for k in required):
                    self.send_error(400, "Missing fields")
                    return

                # Insert or Update
                # For MVP, just Insert
                cur.execute("""
                    INSERT INTO routes (user_id, name, start_station_id, end_station_id, target_arrival_time, alert_lead_time_minutes, days_of_week)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING route_id
                """, (
                    data["user_id"], 
                    data["name"], 
                    data["start_station_id"], 
                    data["end_station_id"],
                    data.get("target_arrival_time"),
                    data.get("alert_lead_time_minutes", 15),
                    data.get("days_of_week", [])
                ))
                
                new_id = cur.fetchone()[0]
                conn.commit()
                
                self.send_json({"route_id": new_id}, status=201)

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
