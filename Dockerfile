FROM ubuntu:20.04

WORKDIR .

RUN apt-get update && apt-get install --yes --no-install-recommends python3 python3-pip && \
	python3 -m pip install grpcio && \
	python3 -m pip install grpcio-tools

COPY . .

ENTRYPOINT ["python3", "server.py"]