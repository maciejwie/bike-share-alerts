from fastapi import FastAPI

from routers import admin, cron, monitor, routes, stations, trips, users

app = FastAPI(root_path="/api")


app.include_router(routes.router)
app.include_router(stations.router)
app.include_router(monitor.router)
app.include_router(admin.router)
app.include_router(trips.router)
app.include_router(cron.router)
app.include_router(users.router)
