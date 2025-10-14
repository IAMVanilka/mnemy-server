import logging
import shutil
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, HTTPException, Form, Depends, Header
from fastapi.responses import StreamingResponse, FileResponse
from starlette.responses import RedirectResponse

from modules.file_manager import (check_files, delete_files, get_backups_info, unpack_tar_archive,
                                  create_archive_chunk_generator, get_files, create_backup, read_saves_directory)
from modules.models import GameFilesData, SavesBackup
from modules.sqls import get_user, check_last_sync_date, update_sync_date, delete_sync_data


logger = logging.getLogger(__name__)

files_router = APIRouter(prefix='/files', tags=["Files 📂"])
manage_router = APIRouter(prefix='/manage', tags=["Manager 🛠️"])

def check_api_token(x_api_token:  str = Header(..., description="API token for authentication")):
    if x_api_token:
        user = get_user(token=x_api_token)
        if user is False:
            raise HTTPException(status_code=403, detail="Invalid or expired token")
        return user
    elif x_api_token is None:
        raise HTTPException(status_code=401, detail="X-API-Token header missing")
    else:
        raise HTTPException(status_code=403, detail="Invalid or expired token")


@files_router.post('/check_files')
async def sync_files(files_data: GameFilesData, user = Depends(check_api_token)):
    username = user.username
    if files_data.last_sync_date is None:
        status = True
    else:
        status = check_last_sync_date(username, files_data.game_name, files_data.last_sync_date)

    if status is True:
        if not os.path.exists(f"saves/{username}/{files_data.game_name}"):
            print(f"Папка 'saves/{username}/{files_data.game_name}' не обнаружена! Создаю новую...")
            os.makedirs(f"saves/{username}/{files_data.game_name}")

        if not os.path.exists(f"resources/{username}/{files_data.game_name}"):
            os.makedirs(f"resources/{username}/{files_data.game_name}")

        check_info = await check_files(username, files_data)

        if check_info['extra_on_server'] is not None:
            await delete_files(check_info['extra_on_server'], files_data.game_name, username)

        update_sync_date(username, files_data.game_name)

        if check_info == {}:
            return {"files_data": 'OK'}
        else:
            return {"files_data":check_info}
    elif status is False:
        return RedirectResponse(url="/files/download_data")
    else:
        raise HTTPException(
            status_code=500,
            detail="Server check sync time error!"
        )


@files_router.post('/upload_data')
async def upload_data(file: UploadFile, game_name: str = Form(...), user = Depends(check_api_token)):
    username = user.username
    temp_path = f"tmp_data/{username}/uploaded_archive_{hash(file.filename)}"

    try:
        await get_files(file, game_name, temp_path, username)
        await create_backup(game_name, username)

        return {"status": "success", "extracted_to": f"saves/{username}/{game_name}"}

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(500, f"Серверу не удалось получить/распаковать данные: {str(e)}")


@files_router.get("/download_data")
async def download_data(game_name: str, user = Depends(check_api_token)):
    username = user.username
    if os.path.exists(f"saves/{username}/{game_name}") and len(os.listdir(f"saves/{username}/{game_name}")) == 0:
        raise HTTPException(404, f"Saves doesn't exist!")
    elif not os.path.exists(f"saves/{username}/{game_name}"):
        raise HTTPException(404, f"Saves doesn't exist!")
    else:
        return StreamingResponse(
            create_archive_chunk_generator(f"saves/{username}/{game_name}"),
            media_type="application/gzip",
            headers={"Content-Disposition": f"attachment; filename={game_name.replace(" ", "_")}-saves.tar.gz"}
        )

@files_router.get('/get_image/{game_name}')
async def get_image(game_name: str, user = Depends(check_api_token)):
    username = user.username
    try:
        # Валидация имени файла (защита от path traversal)
        if '..' in game_name or '/' in game_name or '\\' in game_name:
            raise HTTPException(
                status_code=400,
                detail="Invalid game name -_-"
            )

        file_path = f"resources/{username}/{game_name}.jpg"

        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=404,
                detail="Image file not found!"
            )

        return FileResponse(file_path)

    except HTTPException:
        raise
    except PermissionError:
        logger.error(f"Permission denied when accessing image: {game_name}")
        raise HTTPException(
            status_code=500,
            detail="Permission denied when accessing image file"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_image for {game_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
@files_router.get("/get_backups_data")
async def get_backups_data(user = Depends(check_api_token)):
    backups_data = get_backups_info(user.username)
    if backups_data is False:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )
    return backups_data

@files_router.post("/restore_backup")
async def restore_backup(backup_data: SavesBackup,  user = Depends(check_api_token)):
    if os.path.exists(f'saves/{user.username}/{backup_data.game_name}'):
        shutil.rmtree(f'saves/{user.username}/{backup_data.game_name}')

    status = await unpack_tar_archive(f"backups/{user.username}/{backup_data.game_name}/{backup_data.backup_name}",
                                      f"saves/{user.username}/{backup_data.game_name}")

    if status is True:
        return {"msg": f"Backup '{backup_data.backup_name}' for game '{backup_data.game_name}' has been restored!"}
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )

@files_router.delete("/delete_backup")
async def delete_backup(backup_data: SavesBackup,  user = Depends(check_api_token)):
    if os.path.exists(f"backups/{user.username}/{backup_data.game_name}/{backup_data.backup_name}"):
        os.remove(f"backups/{user.username}/{backup_data.game_name}/{backup_data.backup_name}")
        return {"msg":f"Backup '{backup_data.backup_name}' for game '{backup_data.game_name}'"}
    else:
        raise HTTPException(
            status_code=204,
            detail=f"Backup '{backup_data.backup_name}' for game '{backup_data.game_name}' doesnt exist."
        )

@manage_router.delete('/delete/game/{game_name}')
async def delete_game(game_name: str, delete_backups: bool = False, user = Depends(check_api_token)):
    username = user.username
    try:
        shutil.rmtree(f'saves/{username}/{game_name}')
        if delete_backups and os.path.exists(f"backups/{username}/{game_name}"):
            shutil.rmtree(f"backups/{username}/{game_name}")
            if os.path.exists(f'resources/{username}/{game_name}'):
                shutil.rmtree(f'resources/{username}/{game_name}')
            delete_sync_data(username, game_name)
            return {'message': 'Game successfully deleted with all backups!'}
        else:
            return {'message': 'Game successfully deleted!'}
    except FileNotFoundError:
        raise HTTPException(
            status_code=204,
            detail=f"Игры с именем '{game_name}' не существует.")


@manage_router.patch('/update_game/{game_name}')
async def change_game_data(game_name: str, new_game_name: str, user=Depends(check_api_token)):
    username = user.username

    if not game_name or not new_game_name:
        raise HTTPException(status_code=400, detail="Game names cannot be empty")

    base_dirs = [
        f"saves/{username}",
        f"backups/{username}",
        f"resources/{username}"
    ]

    old_paths = [
        Path(f"{base_dir}/{game_name}") for base_dir in base_dirs
    ]
    new_paths = [
        Path(f"{base_dir}/{new_game_name}") for base_dir in base_dirs
    ]

    missing_paths = [old_path for old_path in old_paths[:2] if not old_path.exists()]
    if missing_paths:
        missing_str = ", ".join([str(path) for path in missing_paths])
        raise HTTPException(
            status_code=404,
            detail=f"Game directories not found: {missing_str}"
        )

    existing_new_paths = [new_path for new_path in new_paths if new_path.exists()]
    if existing_new_paths:
        existing_str = ", ".join([str(path) for path in existing_new_paths])
        raise HTTPException(
            status_code=409,
            detail=f"New game directories already exist: {existing_str}"
        )

    moved_paths = []
    try:
        for old_path, new_path in zip(old_paths, new_paths):
            shutil.move(str(old_path), str(new_path))
            moved_paths.append(old_path)

        return {
            'message': f'Game {game_name} successfully renamed to {new_game_name}!',
            'renamed_paths': [str(path) for path in new_paths]
        }

    except PermissionError:
        for old_path, new_path in zip(moved_paths, new_paths):
            if new_path.exists():
                shutil.move(str(new_path), str(old_path))
        raise HTTPException(
            status_code=403,
            detail="Permission denied during rename operation"
        )

    except OSError as e:
        for old_path, new_path in zip(moved_paths, new_paths):
            if new_path.exists():
                shutil.move(str(new_path), str(old_path))
        print(e)
        raise HTTPException(
            status_code=500,
            detail=f"File system error during rename: {str(e)}"
        )

    except Exception as e:
        for old_path, new_path in zip(moved_paths, new_paths):
            if new_path.exists():
                shutil.move(str(new_path), str(old_path))
        print(e)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during rename: {str(e)}"
        )


@manage_router.get('/get_games_data')
async def get_games_data(user = Depends(check_api_token)):
    try:
        games_list = await read_saves_directory(user.username)
        if games_list is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to read games directory"
            )
        return {"games_list": games_list}
    except FileNotFoundError:
        logger.error("Games directory not found")
        raise HTTPException(
            status_code=500,
            detail="Games directory not found"
        )
    except PermissionError:
        logger.error("Permission denied when accessing games directory")
        raise HTTPException(
            status_code=500,
            detail="Permission denied when accessing games directory"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_games_data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@manage_router.get('/check_x_token')
async def check_x_token(user = Depends(check_api_token)):
    return {'token_status': True}

@manage_router.get('/health')
async def check_server_status():
    return {'status': 'server online'}
