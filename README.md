# Mafia on GRPC | VoiceChat on PyAudio

---

<h1 align="center">Практика 2</h1>

#### Разработка приложения на основе gRPC.

Инструкция по запуску.

---

### 0. Установка зависимостей

Проверяем, что мы в нужном месте.

```
cd Mafia
```

Далее:

```
sudo make apt_get
sudo make requirements
python3 setup.py install
```

Для Mac с чипом M1/M2 (дополнительно):

```
pip install grpcio
```

---

### 1. Запускаем сервер

``` 
RUN_ARGS="--host 0.0.0.0 --port 50051" make server
```

---

### 2. Запускаем клиента(ов)

``` 
RUN_ARGS="--host 0.0.0.0 --port 50051 --nickname // Вводим имя клиента //" make client
```

---

<h1 align="center">Практика 3</h1>

#### Реализация чата с использованием очередей сообщений. Голосовой чат на сокетах.

Инструкция по запуску.



---

### 0. Установка зависимостей

Проверяем, что мы в нужном месте.

```
cd Voice
```

Для Linux/Mac on Intel:

``` 
sudo make apt_get
sudo make install
python3 setup.py install
```

Для Mac с чипом M1/M2:

Используемый Makefile : Makefile_mac

Рекомендуется переименовать его в Makefile, либо использовать ```make -f Makefile_mac``` в последующих командах.

_Чиним проблемы с pyaudio_

```
brew install portaudio
brew link portaudio
brew --prefix portaudio
// Копируем путь: Cmd + C //
sudo nano $HOME/.pydistutils.cfg
// Вставляем следующее //
[build_ext]
include_dirs=<// Cmd + V //>/include/
library_dirs=<// Cmd + V //>/lib/
// Заменив Cmd + V на наш путь, продолжаем //
pip install pyaudio
```

Если проблемы с запуском останутся, то решение для PyCharm:

Preferences -> Python Interpreter -> // Добавление библиотек, недоступных на М1, вручную //

Ошибка "No module named ..." чинится следующим образом:

```
cd ../ <--- Находимся в корне репозитория
export PYTHONPATH=$PYTHONPATH:`pwd` 
```

---

### 1. Запускаем сервер

``` 
RUN_ARGS="--host 0.0.0.0 --port 10080" make server
```

---

### 2. Запускаем клиента(ов)

``` 
RUN_ARGS="--host 0.0.0.0 --port 10080 --username // Вводим имя клиента //" make client
```

---
