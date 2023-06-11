FROM python:3.9-slim

EXPOSE 50051

WORKDIR /mafia
COPY . .

RUN apt-get update && apt-get install make
RUN make requirements

ENTRYPOINT [ "make", "server" ]
