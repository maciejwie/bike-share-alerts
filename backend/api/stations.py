from http.server import BaseHTTPRequestHandler
import os
import json
import psycopg2
from urllib.parse import urlparse

# Vercel Serverless Function
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"DATABASE_URL not set")
            return

        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # Fetch latest status for all stations
            # We join stations metadata with the latest status
            # For MVP, just fetching from stations table if populated, 
            # or distinct from station_status if we rely on that.
            # Let's assume we want the latest status.
            
            # Efficient query for latest status per station is distinct on station_id order by time desc
            # But with TimescaleDB/Postgres, we can use DISTINCT ON
            
            query = """
                SELECT DISTINCT ON (station_id)
                    station_id, num_bikes_available, num_ebikes_available, num_docks_available, time
                FROM station_status
                ORDER BY station_id, time DESC
            """
            
            cur.execute(query)
            rows = cur.fetchall()
            
            stations = []
            for row in rows:
                stations.append({
                    "id": row[0],
                    "bikes": row[1],
                    "ebikes": row[2],
                    "docks": row[3],
                    "last_updated": row[4].isoformat()
                })
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"stations": stations}).encode('utf-8'))
            
            cur.close()
            conn.close()
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
