import uvicorn

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from modules.admin_panel.admin_panel import panel_router, users_panel_router
from modules.admin_panel.auth_controller import  panel_auth_router
from modules.controllers import files_router, manage_router
from modules.file_manager import create_all_folders

app = FastAPI()
routers = [files_router, manage_router, panel_router, panel_auth_router, users_panel_router]

app.mount("/static", StaticFiles(directory="modules/admin_panel/static"), name="admin_static")

for router in routers:
    app.include_router(router)

if __name__ == "__main__":
    create_all_folders()
    uvicorn.run(app="main:app", reload=True)