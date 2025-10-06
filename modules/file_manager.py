import hashlib
import json
import tarfile
import os

from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from modules.models import GameFilesData
import traceback

with open("settings.json", "r") as settings_file:
    backups_limit = json.load(settings_file)['backups_limit']

async def hash_generator(game_name: str, username: str) -> dict:
    """Сканирует папку и генерирует словарь {'file_path': 'md5_hash'}"""

    base_dir = f"saves/{username}/{game_name}"

    if not os.path.exists(base_dir):
        os.mkdir(base_dir)

    files_data = dict()

    def scan_directory(directory):
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file():
                    with open(entry.path, "rb") as file:
                        md5_hash = hashlib.file_digest(file, 'md5')
                        files_data[(entry.path.split(game_name)[1])] = md5_hash.hexdigest()
                elif entry.is_dir():
                    scan_directory(entry.path)

    scan_directory(base_dir)
    return files_data

async def check_files(username: str, files_data: GameFilesData):
    """Сверяет хэши файлов на сервере с клиентскими (клиентские файлы считаются эталоном)
        :param files_data: GameFilesData object
        :returns {files sync info}
    """

    # Текущие хэши на сервере (локальные)
    server_hashes: dict[str, str] = await hash_generator(files_data.game_name, username)
    # Эталонные хэши — от клиента
    client_hashes: dict[str, str] = files_data.files_data

    # Множества файлов
    server_files: set = set(server_hashes.keys())
    client_files: set = set(client_hashes.keys())

    # 🔹 Чего НЕ хватает на сервере (но есть у клиента) → нужно добавить
    missing_on_server: list[str] = sorted(client_files - server_files)

    # 🔹 Что лишнее на сервере (нет у клиента) → можно удалить (по политике)
    extra_on_server: list[str] = sorted(server_files - client_files)

    # 🔹 Общие файлы — проверяем хэши
    common_files: set[str] = server_files & client_files
    mismatched_hashes: list[str] = sorted(
        file for file in common_files
        if server_hashes[file] != client_hashes[file]  # сервер ≠ клиент (клиент — прав)
    )

    # === Отчёт ===
    print("=== Проверка сервера по эталону клиента ===")

    if missing_on_server:
        print("🔴 Отсутствуют на сервере (должны быть добавлены):")
        for file in missing_on_server:
            print(f"   - {file}")
    else:
        print("🟢 Все файлы клиента присутствуют на сервере.")

    if extra_on_server:
        print("🟡 Лишние файлы на сервере (не в эталоне клиента):")
        for file in extra_on_server:
            print(f"   - {file}")
    else:
        print("🟢 Нет лишних файлов на сервере.")

    if mismatched_hashes:
        print("🟠 Хэши не совпадают (сервер устарел, нужно обновить):")
        for file in mismatched_hashes:
            print(f"   - {file} | Сервер: {server_hashes[file]}, Клиент (эталон): {client_hashes[file]}")
    else:
        print("🟢 Все хэши совпадают с эталоном клиента.")

    print("==================================")

    if missing_on_server is None and extra_on_server is None and mismatched_hashes is None:
        return {}

    return {
        "missing_on_server": missing_on_server,      # нужно получить от клиента
        "extra_on_server": extra_on_server,          # можно удалить
        "mismatched_hashes": mismatched_hashes,      # нужно обновить с клиента
        "is_up_to_date": not (missing_on_server or mismatched_hashes),
        "needs_update": len(missing_on_server) + len(mismatched_hashes)
    }


async def delete_files(files_paths: list, game_name: str, username: str):
    """Просто удаляет указанные файлы..."""

    for file in files_paths:
        file_full_path = f"saves/{username}/{game_name}{file}"
        if os.path.exists(file_full_path):
            os.remove(file_full_path)
            print(f"Удаляю файл {file_full_path}")
        else:
            print(f"Не удалось удалить файл {file_full_path}! Файл не найден.")

        print("Лишние файлы были удалены!")


def writer(folder_path: str, tar_path: Optional[str] = None, use_pipe: bool = False):
    """
    Рекурсивно архивирует папку в .tar.gz.

    - Если use_pipe=True → создаёт pipe, запускает архивацию в фоновом потоке,
      возвращает read-конец pipe для чтения (int fd).
    - Если use_pipe=False → архивирует в файл tar_path, возвращает True/False.
    """
    def _write_tar(folder_path: str, name: Optional[str] = None, fileobj=None) -> bool:
        """Внутренняя функция: непосредственно создаёт tar-архив"""
        try:
            tar_args = {"fileobj": fileobj} if fileobj else {"name": name}
            with tarfile.open(mode="w:gz", compresslevel=6, **tar_args) as tar:
                def process_directory(dir_path):
                    with os.scandir(dir_path) as entries:
                        for entry in entries:
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    relative_path = Path(entry.path).relative_to(folder_path)
                                    tar.add(entry.path, arcname=str(relative_path))
                                elif entry.is_dir(follow_symlinks=False):
                                    process_directory(entry.path)
                            except (OSError, PermissionError) as e:
                                print(f"⚠️  Пропущен элемент {entry.path}: {e}")
                                continue

                process_directory(folder_path)
            return True
        except Exception as e:
            print(f"❌ Tar creation error: {e}")
            traceback.print_exc()
            return False

    if use_pipe:
        import threading

        if tar_path is not None:
            raise ValueError("Cannot specify tar_path when use_pipe=True")

        read_fd, write_fd = os.pipe()


        def writer_worker():
            """Фоновый поток: пишет архив в write-конец pipe"""
            success = False
            try:
                with os.fdopen(write_fd, "wb") as wf:
                    success = _write_tar(folder_path, fileobj=wf)
            except Exception as e:
                print(f"❌ Writer worker error: {e}")
                traceback.print_exc()
            finally:
                try:
                    os.close(write_fd)
                except OSError:
                    pass
                if not success:
                    try:
                        os.close(read_fd)
                    except OSError:
                        pass

        thread = threading.Thread(target=writer_worker, daemon=True)
        thread.start()
        return read_fd

    else:
        if tar_path is None:
            raise ValueError("tar_path must be provided when use_pipe=False")
        return _write_tar(folder_path, name=tar_path)


async def create_archive_chunk_generator(base_dir: str, CHUNK_SIZE: int = 65536):
    """
    Асинхронный генератор чанков .tar.gz архива.
    Архивация происходит в фоновом потоке, данные читаются через pipe.
    """
    read_fd = writer(folder_path=base_dir, use_pipe=True)
    if read_fd is None:
        raise RuntimeError("Writer failed to start")

    try:
        with os.fdopen(read_fd, "rb") as rf:
            while True:
                chunk = rf.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
    except BrokenPipeError:
        print("ℹ️  Pipe closed early (likely writer finished or encountered error)")
    except Exception as e:
        print(f"❌ Chunk reader error: {e}")
        raise
    finally:
        try:
            os.close(read_fd)
        except OSError:
            pass


async def get_files(file: UploadFile, game_name: str, temp_path: str, username: str):
    """
    Получает архив во временную директорию, распаковывает архив в директорию игры, удаляет временный архив
    """

    import aiofiles

    if not os.path.exists(f'tmp_data/{username}'):
        os.makedirs(f'tmp_data/{username}')

    async with aiofiles.open(temp_path, "wb") as f:
        while chunk := await file.read(65536):
            await f.write(chunk)

    with tarfile.open(temp_path, "r:gz") as tar:
        if not os.path.exists(f"saves/{username}/{game_name}"):
            os.mkdir(f"saves/{username}/{game_name}")

        tar.extractall(path=f"saves/{username}/{game_name}")

    os.remove(temp_path)


async def unpack_tar_archive(file_path: str, destination_folder: str):
    with tarfile.open(file_path, "r:gz") as tar:
        if not os.path.exists(destination_folder):
            os.mkdir(destination_folder)

        tar.extractall(path=destination_folder)

        return True


async def create_backup(game_name: str, username: str):
    """
    Создает backup сохранения в виде tar архива.
    """

    from datetime import datetime, UTC
    import os

    time_now_utc = datetime.now(UTC).strftime("%Y-%d-%m_%H:%M:%S")

    if not os.path.exists(f"backups/{username}/{game_name}"):
        os.makedirs(f"backups/{username}/{game_name}")
    else:
        backup_files = [f for f in os.listdir(f"backups/{username}/{game_name}") if f.endswith('.tar.gz')]
        i = len(backup_files)

        if i >= backups_limit:
            backup_files.sort()

            excess_count = i - backups_limit + 1
            for j in range(min(excess_count, len(backup_files))):
                try:
                    os.remove(f"backups/{username}/{game_name}/{backup_files[j]}")
                    print(f"Удален старый бэкап: {backup_files[j]}")
                except Exception as e:
                    print(f"Ошибка при удалении бэкапа {backup_files[j]}: {e}")

    writer_status = writer(folder_path=f"saves/{username}/{game_name}", tar_path=f"backups/{username}/{game_name}/{time_now_utc}.tar.gz")

    return writer_status

async def read_saves_directory(username: str):
    list_of_games = list()
    entries = os.scandir(f'saves/{username}')
    for entry in entries:
        list_of_games.append(entry.name)

    return list_of_games

def create_all_folders():
    if not os.path.exists('backups'):
        os.mkdir('backups')
    if not os.path.exists('saves'):
        os.mkdir('saves')
    if not os.path.exists('resources'):
        os.mkdir('resources')

def get_backups_info(username):
    """
    Возвращает информацию о бэкапах для указанного пользователя.
    Формат результата:
    {
        "test": [
            {
                "filename": "2025-29-09_09:01:11.tar.gz",
                "size_bytes": 123456
            },
            ...
        ],
        ...
    }
    """
    base_path = f"backups/{username}"
    backups_info = {}

    if not os.path.exists(base_path):
        return backups_info

    try:
        with os.scandir(base_path) as entries:
            for entry in entries:
                if entry.is_dir():
                    game_name = entry.name
                    game_backups = []
                    game_path = entry.path

                    with os.scandir(game_path) as files:
                        for file_entry in files:
                            if file_entry.is_file() and file_entry.name.endswith(".tar.gz"):
                                filename = file_entry.name

                                file_stat = file_entry.stat()
                                game_backups.append({
                                    "filename": filename,
                                    "size_bytes": file_stat.st_size,
                                })

                    backups_info[game_name] = game_backups

    except Exception as e:
        print(f"Ошибка при чтении бэкапов для {username}: {e}")
        return False

    return backups_info
