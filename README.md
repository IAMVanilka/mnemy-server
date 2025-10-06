# 🖥️ Mnemy Server (ru 🇷🇺)

![Mnemy Logo](logo.png)

> ⚠️ Данный репозиторий лишь серверная часть приложения, для того чтобы скачать клиентскую часть перейдите сюда: [mnemy-client](https://github.com/IAMVanilka/Mnemy)

**Mnemy** автоматически синхронизирует ваши игровые сохранения с личным сервером — чтобы вы никогда не потеряли свой прогресс.


## 📥 Установка

⚠️ Приложение разрабатывалось на **python3.13**, я не могу быть уверен в корректной работоспособности сервера на младших версиях!

1. Клонируйте данный репозиторий: 
```bash
git clone https://github.com/IAMVanilka/mnemy-sever.git
```
2. Создайте виртуальное окружение python: 
```
bash python3.13 -m venv venv
```
3. Запустите виртуальное окружение: 
```bash
source venv/bin/activate
```
4. Установите зависимости: 
```bash
pip install -r requirements.txt
```
5. Запустите генератор хэшэй с сгенерируйте там хэш для `PANEL_PASSWORD` и ключ для `SECRET_KEY`.
```bash
python3.13 modules/pass_hash_generator.py
```
6. Создайте `secrets.env` и укажите там: `PANEL_USERNAME`, а в `PANEL_PASSWORD` укажите хэш, который вы сгенерировали. Укажите сгенерированный `SECRET_KEY` для шифровки данных.
7. Запустите приложение: 
```bash
python3.13 main.py
```
**После запуска админ панель будет доступна по эндпоинту** `http/https://your-server-domain:8000/panel/`

*При необходимости создайте сервис в `systemctl`, настройте `nginx` и тд.*

✅ Имеется **автоматическая установка** для этого перейдите в [**releases**](https://github.com/IAMVanilka/mnemy-server/releases) и скачайте отуда bash скрипт установки.

> Carefully archived. Faithfully remembered. Mnemy.

---

# 🖥️ Mnemy Server (en 🇬🇧 )

> ⚠️ This repository contains only the server-side component of the application. To download the client-side part, please go here: [mnemy-client](https://github.com/IAMVanilka/Mnemy)

**Mnemy** automatically syncs your game saves to your personal server—so you never lose your progress.

## 📥 Installation

⚠️ The application was developed using **Python 3.13**. I cannot guarantee proper functionality on older Python versions!

1. Clone this repository:  
   ```bash
   git clone https://github.com/IAMVanilka/mnemy-server.git
   ```
2. Create python virtual enviroment: 
```
bash python3.13 -m venv venv
```
3. Run venv: 
```bash
source venv/bin/activate
```
4. Install dependencies: 
```bash
pip install -r requirements.txt
```
5. Run the hash generator and generate a hash for `PANEL_PASSWORD` and a key for `SECRET_KEY`.
```bash
python3.13 modules/pass_hash_generator.py
```
6. Create `secrets.env` and specify `PANEL_USERNAME` there, and set `PANEL_PASSWORD` to the hash you generated. Specify the generated `SECRET_KEY` to encrypt the data.
7. Run the application:
```bash
python3.13 main.py
```

**After launch, the admin panel will be accessible via the endpoint** `http/https://your-server-domain:8000/panel/`

*Optionally, you can set up a `systemctl` service, configure `nginx`, etc.*

✅ Automatic installation is available! Visit the [**releases page**](https://github.com/IAMVanilka/mnemy-server/releases) and download the installation bash script.

> Carefully archived. Faithfully remembered. Mnemy.
