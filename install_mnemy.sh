#!/bin/bash

set -e  # Прервать при ошибке

# === 1. Настройки ===
REPO_URL="https://github.com/IAMVanilka/mnemy-server.git"
APP_NAME="Mnemy-server"
APP_USER="mnemy-app"
PROJECT_DIR="/opt/$APP_NAME"
VENV_PATH="$PROJECT_DIR/venv"
USER="$APP_USER"
GROUP="$APP_USER"

echo "🚀 Начинаем установку приложения: $APP_NAME"

# Создаём пользователя, если не существует
if ! id "$APP_USER" &>/dev/null; then
    echo "👤 Создание системного пользователя: $APP_USER"
    sudo useradd --system --no-create-home --user-group "$APP_USER"
fi

# === 2. Клонирование репозитория ===
echo "📥 Клонирование репозитория..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown -R $USER:$GROUP "$PROJECT_DIR"
cd "$PROJECT_DIR"

if [ -d ".git" ]; then
    sudo -u $USER git pull
else
    sudo -u $USER git clone "$REPO_URL" .
fi

# === 3. Создание venv и установка зависимостей ===
echo "🐍 Проверка наличия Python 3.13..."

if ! command -v python3.13 &> /dev/null; then
    echo "❌ Python 3.13 не найден в системе."
    echo "   Ваше приложение требует Python 3.13 для стабильной работы."
    echo "   Возможные решения:"
    echo "     • Установите Python 3.13 (например, через deadsnakes PPA на Ubuntu):"
    echo "         sudo add-apt-repository ppa:deadsnakes/ppa"
    echo "         sudo apt update"
    echo "         sudo apt install python3.13 python3.13-venv python3.13-dev"
    echo "     • Или обновите requirements.txt и код для поддержки более старой версии Python."
    echo ""
    echo "⚠️  Продолжение без Python 3.13 может привести к ошибкам или нестабильной работе!"
    read -p "Продолжить установку без Python 3.13? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "🛑 Установка прервана."
        exit 1
    else
        echo "⚠️  Продолжаем на свой страх и риск..."
        PYTHON_CMD="python3"  # fallback
    fi
else
    PYTHON_CMD="python3.13"
fi

echo "🐍 Создание виртуального окружения..."
sudo -u $USER $PYTHON_CMD -m venv "$VENV_PATH"
sudo -u $USER "$VENV_PATH/bin/pip" install --upgrade pip
sudo -u $USER "$VENV_PATH/bin/pip" install -r requirements.txt

# === 4–7. Генерация secrets.env ===
echo "🔒 Настройка секретов..."

# Запрос логина и пароля
read -p "Введите логин для админа: " ADMIN_LOGIN
read -s -p "Введите пароль для админа: " ADMIN_PASSWORD
echo

# Генерация хеша пароля через ваш модуль
echo "🔑 Генерация хеша пароля..."
HASHED_PASSWORD=$(
    sudo -u $USER "$VENV_PATH/bin/python" -c "
import sys
sys.path.insert(0, '.')
from passlib.hash import bcrypt
print(bcrypt.hash(str('$ADMIN_PASSWORD')))
"
)

# Генерация secret key
SECRET_KEY=$(
    sudo -u $USER "$VENV_PATH/bin/python" -c "
import secrets
print(secrets.token_urlsafe(32))
"
)

# Создание secrets.env
sudo -u "$USER" sh -c 'cat > secrets.env' <<EOF
PANEL_USERNAME=$ADMIN_LOGIN
PANEL_PASSWORD=$HASHED_PASSWORD
SECRET_KEY=$SECRET_KEY
EOF

sudo chown $USER:$GROUP secrets.env
sudo chmod 600 secrets.env

echo "✅ secrets.env создан"

# === 8. Создание systemd .service ===
echo "⚙️ Создание systemd сервиса..."

SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Carefully archived. Faithfully remembered. Mnemy.
After=network.target

[Service]
User=$USER
Group=$GROUP
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/secrets.env
ExecStart=$VENV_PATH/bin/python3 $PROJECT_DIR/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

# === 9. Запуск проекта ===
echo "🚀 Запуск сервиса..."
sudo systemctl enable --now "$APP_NAME.service"

echo "✅ Деплой завершён!"
echo "Сервис запущен: sudo systemctl status $APP_NAME"
echo "Логи: sudo journalctl -u $APP_NAME -f"
echo "Доступ к админ панели по пути /panel/"
