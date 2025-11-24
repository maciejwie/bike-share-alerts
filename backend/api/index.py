from fastapi import FastAPI

from routers import admin, monitor, routes, stations

app = FastAPI()

app.include_router(routes.router)
app.include_router(stations.router)
app.include_router(monitor.router)
app.include_router(admin.router)
