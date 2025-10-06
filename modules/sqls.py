from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, declarative_base

from datetime import datetime, UTC

engine = create_engine(
    "sqlite:///./users.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    pool_pre_ping=True,
    echo=False
)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    api_token = Column(String, unique=True)

    def __str__(self):
        return f"User(id={self.id}, username={self.username}, token={self.api_token})"

    def __repr__(self):
        return f"User(id={self.id}, username={self.username}, token={self.api_token})"

class SyncData(Base):
    __tablename__ = "sync_data"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    game_name = Column(String)
    last_sync_date = Column(DateTime)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def create_session():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def add_user(username: str, token: str) -> bool|str:
    try:
        with create_session() as session:
            existing = session.query(User).filter(
                (User.username == username) | (User.api_token == token)
            ).first()

            if existing:
                print(f"[БД] Пользователь {username} или токен уже существуют")
                return 'already exists'

            new_user = User(username=username, api_token=token)
            session.add(new_user)
            session.commit()
        return True
    except Exception as e:
        print("[БД] Ошибка при создании нового пользователя! ", e)
        return False

def delete_user(username: str) -> bool:
    try:
        with create_session() as session:
            session.query(User).filter(User.username==username).delete()
            session.commit()
        return True
    except Exception as e:
        print("[БД] Ошибка при удалении пользователя! ", e)
        return False

def get_user(username: str = None, token: str = None, all_users=False):
    try:
        with create_session() as session:
            if all_users:
                users = session.query(User).all()
                return users

            if username:
                user = session.query(User).filter(User.username==username).first()
            elif token:
                user = session.query(User).filter(User.api_token == token).first()
            elif username and token:
                user = session.query(User).filter(User.username == username, User.api_token == token).first()

            if user is None:
                print(f"[БД] Ошибка! Пользователь с заданным именем или токеном не найден!")
                return False

        return user
    except Exception as e:
        print("[БД] Ошибка при получении пользователя! ", e)
        return False

def add_sync_date(username: str, game_name: str):
    try:
        with create_session() as session:
            existing = session.query(SyncData).filter(
                SyncData.game_name == game_name,
                SyncData.username == username
            ).first()

            if existing:
                print(f"[БД] Запись для игры {game_name} пользователя {username} уже существует.")
                return

            new_sync = SyncData(
                username=username,
                game_name=game_name,
                last_sync_date=datetime.now(UTC)
            )
            session.add(new_sync)
            session.commit()
            print(f"[БД] Добавлена новая запись для игры {game_name} пользователя {username}.")
    except IntegrityError as e:
        print(f"[БД] Конфликт при добавлении записи для игры {game_name} пользователя {username}."
              f" Возможно, такая игра уже есть. Текст ошибки: ", e)
    except Exception as e:
        print(f"[БД] Ошибка при добавлении даты сохранения для игры {game_name} пользователя {username}! Текст ошибки: {e}")


def update_sync_date(username: str, game_name: str):
    try:
        with create_session() as session:
            game = session.query(SyncData).filter(SyncData.game_name == game_name, SyncData.username == username).first()
            if game is None:
                add_sync_date(username, game_name)
            else:
                game.last_sync_date = datetime.now(UTC)
                session.commit()
    except Exception as e:
        print(f"[БД] Ошибка при обновлении даты сохранения для игры {game_name} пользователя {username}! Текст ошибки: {e}")

def check_last_sync_date(username: str, game_name: str, user_date: datetime):
    import pytz
    try:
        with create_session() as session:
            game = session.query(SyncData).filter(SyncData.game_name == game_name, SyncData.username == username).first()

            if game is None:
                add_sync_date(username, game_name)
                return True
            local_sync_date = game.last_sync_date
            print("Server saved time:" ,local_sync_date.replace(tzinfo=pytz.utc))
            print("Client saved time:", user_date.astimezone(pytz.utc))
            if local_sync_date.replace(tzinfo=pytz.utc) > user_date.astimezone(pytz.utc):
                return False
            else:
                return True

    except Exception as e:
        print(
            f"[БД] Ошибка при получении даты сохранения для игры {game_name} пользователя {username}! Текст ошибки: {e}")

def delete_sync_data(username: str, game_name: str):
    try:
        with create_session() as session:
            session.query(SyncData).filter(SyncData.username == username, SyncData.game_name == game_name).delete()
            session.commit()
    except Exception as e:
        print(f"[БД] Ошибка при удалении даты сохранения для игры {game_name} пользователя {username}! Текст ошибки: {e}")