import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse

from fastapi_jwt import JwtAuthorizationCredentials

from modules.admin_panel.auth_controller import access_security
from modules.models import Settings
from modules.sqls import add_user, delete_user, get_user

panel_router = APIRouter(prefix='/panel', tags=['Panel 🎛️'])
users_panel_router = APIRouter(prefix='/panel/users', tags=['Panel 🎛️'])

def generate_api_token() -> str:
    return secrets.token_urlsafe(32)

@panel_router.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("modules/admin_panel/static/login.html", "r") as file:
        return HTMLResponse(content=file.read(), status_code=200)

@panel_router.get("/", response_class=HTMLResponse)
async def dashboard_page():
    return FileResponse("modules/admin_panel/static/dashboard.html")

@panel_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page_alt():
    return FileResponse("modules/admin_panel/static/dashboard.html")


@panel_router.get("/test")
async def secure_test(credentials: JwtAuthorizationCredentials = Depends(access_security)):
    return {"message": f"Добро пожаловать, {credentials.subject['username']}!"}

@users_panel_router.get("/get_settings")
async def get_settings(credentials: JwtAuthorizationCredentials = Depends(access_security)):
    import json

    with open('settings.json', 'r') as json_file:
        settings = json.load(json_file)

    return {'settings':{
        'backups_limit':settings['backups_limit'],
        'test_param': settings['test_param']
    }}

@users_panel_router.post("/change_settings")
async def change_settings(settings_data: Settings, credentials: JwtAuthorizationCredentials = Depends(access_security)):
    try:
        with open('settings.json', 'w+') as json_file:
            data_to_load = settings_data.model_dump_json()
            json_file.write(data_to_load)

        return {'msg':"Settings updated!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error! {e}")


@users_panel_router.put("/add", status_code=status.HTTP_201_CREATED)
async def add_new_user(username: str, credentials: JwtAuthorizationCredentials = Depends(access_security)):
    api_token = generate_api_token()
    status_result = add_user(username, api_token)

    if status_result is True:
        return {
            "message": f"User {username} successfully created!",
            "token": api_token
        }
    elif status_result == 'already exists':
        raise HTTPException(status_code=409, detail="User already exists!")
    else:
        raise HTTPException(status_code=500, detail="Internal server error!")

@users_panel_router.delete("/delete")
async def panel_delete_user(username: str, credentials: JwtAuthorizationCredentials = Depends(access_security)):
    status_result = delete_user(username)

    if status_result is True:
        return {
            "message": f"User {username} successfully deleted!",
        }
    else:
        raise HTTPException(status_code=500, detail="Internal server error!")

@users_panel_router.get("/get_users")
async def get_all_users(credentials: JwtAuthorizationCredentials = Depends(access_security)):
    all_users = get_user(all_users=True)

    if all_users:
        return {
            "users":{user.username:user.api_token for user in all_users},
        }
    elif all_users == []:
        raise HTTPException(status_code=204, detail="No users in database!")
    else:
        raise HTTPException(status_code=500, detail="Internal server error!")

