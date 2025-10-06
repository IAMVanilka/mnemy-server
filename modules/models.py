from datetime import datetime

from pydantic import BaseModel

class FileMetadata(BaseModel):
    filename: str

class GameFilesData(BaseModel):
    game_name: str
    files_data: dict
    last_sync_date: datetime | None

class AdminUser(BaseModel):
    username: str
    password: str

class Settings(BaseModel):
    backups_limit: int
    test_param: str

class SavesBackup(BaseModel):
    game_name: str
    backup_name: str