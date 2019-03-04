import socket
from request_hndl import RequestHandler
from io_custom import read_data
import sys

# Server accepts only client at the moment
server_address = "192.168.1.3"
data = [text.rstrip() for text in read_data(sys.argv[1])]
server_port = int(data[0])
window_size = int(data[1])
random_seed = int(data[2])
loss_prob = float(data[3])

# Changed socket.SOCK_STREAM (TCP) to socket.SOCK_DGRAM (UDP)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((server_address, server_port))


# Thread pool to join all of them later to properly terminated the server.
request_pool = []

while True:
    # File request is received here.
    try:
        packet, addr = server_socket.recvfrom(1024)
        request_pool.append(RequestHandler(packet, addr, sys.argv[2], (window_size, random_seed, loss_prob)))
        request_pool[-1].start()
    except KeyboardInterrupt:
        break

server_socket.close()

for hndl in request_pool:
    hndl.join()
