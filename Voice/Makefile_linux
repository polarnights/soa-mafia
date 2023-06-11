server:
	python3 socket_app/server.py ${RUN_ARGS}

client:
	python3 socket_app/client.py ${RUN_ARGS}

apt_get:
	apt-get update
	apt-get install -y python3 python-dev libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0 ffmpeg

requirements:
	python3 -m pip install .

install: apt_get
	python3 -m pip wheel --wheel-dir ./dist .
	python3 -m pip install . --prefer-binary --force-reinstall --find-links ./dist

install_python3:
	apt-get install -y python3