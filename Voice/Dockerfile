FROM ubuntu:latest

EXPOSE 10080

WORKDIR /socket_app
COPY . .

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python make pip
RUN make install

ENTRYPOINT [ "socket-voice-chat-server" ]
