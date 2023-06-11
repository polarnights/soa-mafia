import asyncio
import copy
import json
import random
import os
import time

import sys 
sys.path.append('..')

import grpc
import messenger_pb2
import messenger_pb2_grpc

if __name__ == '__main__':
    grpcServerAddr = os.environ.get('MESSENGER_SERVER_ADDR', 'localhost:51075')
    channel = grpc.insecure_channel(grpcServerAddr)
    stub = messenger_pb2_grpc.MaphiaStub(channel)

    while (True):
        try:
            print('Введите имя:')
            name = input()
            print('')
            stub.Connect(messenger_pb2.InitClient(author=name))
            break
        except grpc.RpcError as e:
            e.details()
            print('Ошибка, попробуйте еще раз.')

    print('Успешно!')
    client_list = stub.GetClients(messenger_pb2.Empty())
    for current in client_list:
        print('Username: ', current.author)

    users = []
    while (True):
        try:
            time.sleep(0.5)
            fl = 1
            tmp = stub.WaitForGame(messenger_pb2.InitClient(author=name))
            for user in tmp:
                if (user.author == 'error'):
                    fl = 0
                users.append(user.author)
            if fl == 0:
                users = []
                continue
            role = stub.GetRole(messenger_pb2.InitClient(author=name)).text
            break
        except grpc.RpcError as rpc_error:
            pass


    print('Игра с пользователями: ', *users, ', роль', role)
    stub.PostMessage(messenger_pb2.ChatMessage(author=name, text="Hello everyone"))
    stub.EndDay(messenger_pb2.InitClient(author=name))
    print('День завершен')

    while (True):
        print('Город засыпает, просыпается мафия')
        print(users)
        print(name)
        if (role == 'mafia'):
            target = random.choice(users)
            while (target == name):
                target = random.choice(users)
            while True:
                try:
                    stub.KillNight(messenger_pb2.InitClient(author=target))
                    print('Мафия сделала свой выбор')
                    break
                except grpc.RpcError as rpc_error:
                    time.sleep(5)
                    pass 

        print('Мафия засыпает, просыпается комиссар')

        if (role == 'policeman'):
            target = random.choice(users)
            while (target == name):
                target = random.choice(users)
            while True:
                try:
                    checker =  stub.Check(messenger_pb2.InitClient(author=target))
                    print('Комиссар сделал свой выбор')
                    if (checker.is_mafia) and (name in users):
                        stub.PostMessage(messenger_pb2.ChatMessage(author=name, text="Mafia is " + target))
                    break
                except grpc.RpcError as rpc_error:
                    time.sleep(5)
                    pass

        print('Комиссар засыпает, просыпается город')

        while True:
            try:
                alive_users = stub.StartDay(messenger_pb2.InitClient(author=name))
                tmp = []
                for user in alive_users:
                    tmp.append(user.author)
                users = tmp
                if name not in tmp:
                    print("Вы погибли")
                for user in users:
                    print("Сейчас в живых: ", user)
                break
            except grpc.RpcError as e:
                time.sleep(5)
                if (e.code() == grpc.StatusCode.FAILED_PRECONDITION):
                    pass
                if (e.code() == grpc.StatusCode.INVALID_ARGUMENT):
                    print("Побеждают мирные жители")
                    print("Для начала новой игры введите имя вновь")
                    sys.exit(0)
                if (e.code() == grpc.StatusCode.ALREADY_EXISTS):
                    print("Побеждает мафия");
                    print("Для начала новой игры введите имя вновь")
                    sys.exit(0)

        morning_messages = stub.GetMessages(messenger_pb2.InitClient(author=name))
        for message in morning_messages:
            print("Сообщение от: ", message.author, " | Текст сообщения:", message.text)

        target = random.choice(users)
        while (target == name):
            target = random.choice(users)

        if name in users:
            print('Голосование против: ', target)
            try:
                stub.VoteKill(messenger_pb2.InitClient(author=target))
            except grpc.RpcError as e:
                time.sleep(5)
                if (e.code() == grpc.StatusCode.FAILED_PRECONDITION):
                    pass
                if (e.code() == grpc.StatusCode.INVALID_ARGUMENT):
                    print("Побеждают мирные жители")
                    print("Для начала новой игры введите имя вновь")
                    sys.exit(0)
                if (e.code() == grpc.StatusCode.ALREADY_EXISTS):
                    print("Побеждает мафия");
                    print("Для начала новой игры введите имя вновь")
                    sys.exit(0)

        print('Голосование по завершению дня')
        stub.EndDay(messenger_pb2.InitClient(author=name))
        print('День окончен')
        time.sleep(10)


print("Спасибо за игру")

