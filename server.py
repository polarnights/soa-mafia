import sys 
sys.path.append('..')

from concurrent import futures
import os
import grpc
import threading
import random
import asyncio

import messenger_pb2
import messenger_pb2_grpc

from google.protobuf.timestamp_pb2 import Timestamp

#always 4 people in a mafia game, assuming people do not disconnect
#and play in their room indefinitely

class MaphiaServicer(messenger_pb2_grpc.MaphiaServicer):

	def __init__(self) -> None:
		self.clients = []
		self.chats = []
		self.status = [] #0 - normal, 1 - mafia, 2 - policeman, -1 - dead
		self.day_time = [] #-1 - zero day, 0 - day, 1 - night mafia, 2 - night policeman
		self.day_count = []
		self.vote_count = []
		self.game = []
		self.total_votes = []
		self.messages = []
		self.message_id = []
		self.game_counter = 0
		self.lock = threading.Lock()

	def Connect(self, request: messenger_pb2.InitClient, context):
		with self.lock:
			for tmp in self.clients:
				if (request.author == tmp) or (request.author == 'error'):
					context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
					context.set_details('Name must be unique, this one is already taken')
					return messenger_pb2.Empty()
			self.clients.append(request.author)
			self.status.append(0)
			self.game.append(0)
			self.message_id.append(0)
			self.vote_count.append(0)
			if len(self.clients) % 4 == 0:
				self.day_time.append(-1)
				self.day_count.append(0)
				self.game_counter += 1
				self.messages.append([])
				self.total_votes.append(0)
				for i in range(4):
					self.game[len(self.game) - i - 1] = self.game_counter
				i, j = random.sample(range(1, 4), 2)
				self.status[len(self.game) - i - 1] = 1
				self.status[len(self.game) - j - 1] = 2
			return messenger_pb2.Empty()

	def GetClients(self, request, context):
		with self.lock:
			i = 0
			for messg in self.clients:
				yield messenger_pb2.InitClient(author=messg)
			return

	def WaitForGame(self, request, context):
		with self.lock:
			i = 0
			for tmp in self.clients:
				if request.author == tmp:
					break
				i += 1
			if self.game[i] == 0:
				yield messenger_pb2.InitClient(author="error")
			else:
				print("game started")
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					fd = i
			for i in range(len(self.clients)):
				if self.game[i] == self.game[fd]:
					yield messenger_pb2.InitClient(author=self.clients[i])
			return
		

	def GetRole(self, request, context):
		with self.lock:
			fd = 0
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					fd = i
			role = 'commoner'
			if (self.status[fd] == 1):
				role = 'mafia'
			if (self.status[fd] == 2):
				role = 'policeman'
			if (self.status[fd] < 0):
				role = 'dead'
			return messenger_pb2.Universal(text=role)


	def EndDay(self, request, context):
		with self.lock:
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					self.day_count[i // 4] += 1
					if self.day_count[i // 4] == 4:
						self.day_time[i // 4] = 1
						self.day_count[i // 4] = 0
			return messenger_pb2.Empty()

	def KillNight(self, request, context):
		with self.lock:
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					print('found target to kill by mafia - ', self.day_time[i // 4])
					if self.day_time[i // 4] != 1:
						context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
						context.set_details('Time is yet to come')
						return messenger_pb2.Empty()
					print('it can be killed')
					self.status[i] = -1
					self.day_time[i // 4] = 2
			return messenger_pb2.Empty()

	def Check(self, request, context):
		with self.lock:
			res = False
			print("Checking if ", request.author, " is mafia")
			for i in range(len(self.clients)):
				if (self.clients[i] == request.author) and (self.day_time[i // 4] != 2):
					context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
					context.set_details('Time is yet to come')
					return messenger_pb2.CheckResult(is_mafia=False)
			for i in range(len(self.clients)):
				if (self.clients[i] == request.author) and (self.status[i] == 1):
					res = True
					self.day_time[i // 4] = 0
				elif (self.clients[i] == request.author):
					self.day_time[i // 4] = 0
			print("done and checked result = ", res)
			return messenger_pb2.CheckResult(is_mafia=res)

	def PostMessage(self, request, context):
		with self.lock:
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					self.messages[i // 4].append(request)

		return messenger_pb2.Empty()

	def GetMessages(self, request, context):
		with self.lock:
			fd = 0
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					fd = i
			while (self.message_id[fd] < len(self.messages[fd // 4])):
				yield self.messages[fd // 4][self.message_id[fd]]
				self.message_id[fd] += 1


	def StartDay(self, request, context):
		with self.lock:
			fd = 0
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					fd = i
			if self.day_time[fd // 4] != 0:
				context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
				context.set_details('Too early retry later')
				return
			alive = 0
			mafias = 0
			for i in range(len(self.clients)):
				if self.game[i] == self.game[fd]:
					if self.status[i] >= 0:
						alive += 1
					if self.status[i] == 1:
						mafias += 1
			if mafias == 0:
				context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
				context.set_details('Mafia lost. Game over')
				return
			if alive - mafias <= mafias:
				context.set_code(grpc.StatusCode.ALREADY_EXISTS)
				context.set_details('Mafia won. Game over')
				return
			for i in range(len(self.clients)):
				if (self.game[i] == self.game[fd]) and (self.status[i] >= 0):
					yield messenger_pb2.InitClient(author=self.clients[i])

	def VoteKill(self, request, context):
		with self.lock:
			fd = 0
			for i in range(len(self.clients)):
				if self.clients[i] == request.author:
					fd = i
			self.vote_count[fd] += 1
			self.total_votes[fd // 4] += 1
			if self.total_votes[fd // 4] == 4:
				self.total_votes[fd // 4] = 0
				opt_ind = -1
				opt_value = 0
				opt_count = 0
				for i in range(len(self.clients)):
					if self.game[i] == self.game[fd]:
						if (opt_ind < 0) or (self.vote_count[i] > opt_value):
							opt_ind = i
							opt_value = self.vote_count[i]
							opt_count = 1
						elif (self.vote_count[i] == opt_value):
							opt_count += 1
						self.vote_count[i] = 0
				if (opt_ind > 0) and (opt_count == 1):
					self.status[opt_ind] = -1
			alive = 0
			mafias = 0
			for i in range(len(self.clients)):
				if self.game[i] == self.game[fd]:
					if self.status[i] >= 0:
						alive += 1
					if self.status[i] == 1:
						mafias += 1
			if mafias == 0:
				context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
				context.set_details('Mafia lost. Game over')
				return messenger_pb2.Empty()
			if alive - mafias <= mafias:
				context.set_code(grpc.StatusCode.ALREADY_EXISTS)
				context.set_details('Mafia won. Game over')
				return messenger_pb2.Empty()

		return messenger_pb2.Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    port = os.environ.get('MESSENGER_SERVER_PORT', 51075)
    messenger_pb2_grpc.add_MaphiaServicer_to_server(
        MaphiaServicer(), server)
    server.add_insecure_port('0.0.0.0:' + str(port))
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
	serve()