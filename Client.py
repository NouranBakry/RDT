from io_custom import read_data
from window import Window
import socket
from Packet import create_udp_packet, create_ack_packet, validate_checksum
import os
import time
import random
import sys

localhost = '192.168.1.3'


class Client:

    def __init__(self, input_file, method):
        self.data = [text.rstrip() for text in read_data(input_file)]
        self.server_port = int(self.data[1])
        self.port_number = int(self.data[2])
        self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_sock.bind((localhost, self.port_number))
        self.file_name = self.data[3]
        self.window_size = int(self.data[4])

        if method in ["RDT", "rdt"]:
            self.method = self.rdt30
        elif method in ["SR", "sr"]:
            self.method = self.selective_repeat
        elif method in ["GBN", "gbn"]:
            self.method = self.GBN
        else:
            raise RuntimeError

    def rdt30(self):
        pkt = create_udp_packet(self.client_sock.getsockname()[1], self.server_port, 0, self.file_name, False)
        self.client_sock.sendto(pkt, (localhost, self.server_port))
        print("CLIENT sent file request.")

        full_data = bytearray()

        # Expected seq number
        seq_no = 0
        ack_pkt = None

        while True:

            data = self.client_sock.recv(256 + 10)

            # Indication that the file is fully sent by the server by sending EOF signal or data is corrupted.
            if data == b'EOF' or not data:
                break

            # Extracting the data from packet received from server
            handler_port = int.from_bytes(data[:2], 'big')
            dest_port = int.from_bytes(data[2:4], 'big')
            msg_len = int.from_bytes(data[4:6], 'big')
            checksum = int.from_bytes(data[6:8], 'big')
            pkt_seq = int.from_bytes(data[8:10], 'big')
            
            if not validate_checksum(data) or seq_no != pkt_seq:
                if ack_pkt is not None:
                    if random.random() < 0.95:
                        print("CLIENT resending ACK", int.from_bytes(ack_pkt, 'big'))
                        self.client_sock.sendto(ack_pkt, (localhost, handler_port))
                    continue

            if validate_checksum(data) and pkt_seq == seq_no:
                print("CLIENT received packet with sequence", pkt_seq)
                full_data.extend(data[10:])
                ack_pkt = create_ack_packet(seq_no)
                if random.random() < 0.95:
                    print("CLIENT resending ACK", int.from_bytes(ack_pkt, 'big'))
                    self.client_sock.sendto(ack_pkt, (localhost, handler_port))
                print("CLIENT sent ACK", seq_no)
                seq_no = seq_no ^ 1
                print("CLIENT expecting packet", seq_no)
                data = None

        # Write file's data on HDD from bytearray.
        with open(os.path.realpath(self.file_name), 'wb') as f:
            f.write(full_data)

        self.client_sock.close()

    def selective_repeat(self):

        # Requesting File From Server
        pkt = create_udp_packet(self.port_number, self.server_port, 0, self.file_name)
        self.client_sock.sendto(pkt, (localhost, self.server_port))

        print("CLIENT sent file request.")
        file_data = bytearray()
        window = Window(self.window_size)

        while True:
            
            # Receive 256 Bytes + 10 Bytes (Header) of data from server.
            data = self.client_sock.recv(256+10)

            # Break when EOF is reached.
            if data == b'EOF' or not data:
                break
            
            # Extracting data from packet.
            handler_port = int.from_bytes(data[:2], 'big')
            dest_port = int.from_bytes(data[2:4], 'big')
            msg_len = int.from_bytes(data[4:6], 'big')
            checksum = int.from_bytes(data[6:8], 'big')
            pkt_seq = int.from_bytes(data[8:10], 'big')

            # If the data is invalid, ignore it.
            if not validate_checksum(data):
                continue

            print("Receving", pkt_seq)

            # Create and acknowledgment packet with the sequence number received
            # And successfully send it with 95% chance.
            ack_pkt = create_ack_packet(pkt_seq)
            if random.random() < 0.95:
                self.client_sock.sendto(ack_pkt, (localhost, handler_port))

            print(window.current_c())
            
            # Only buffer the data that in the current window frame.
            # This is becuase that you should ignore packets received that
            # Client has already buffered, however you still need to send an
            # ACK for those.
            if pkt_seq in window:
                window.buffer_data(data[10:], pkt_seq)

            # Also, Instead of dealing with the base sequence number, Just
            # Buffering every packet and then iterate the current window
            # And breaking when we find the very first unacked packet
            # is a better option.
            for s in window.current_c():
                if s.acked:
                    file_data.extend(s.data)
                    window.update_base()
                else:
                    break

        with open(os.path.realpath(self.file_name), 'wb') as file:
            file.write(file_data)

        self.client_sock.close()

    def GBN(self):

        # Requesting File From Server
        current_seq = 0
        pkt = create_udp_packet(self.port_number, self.server_port, 0, self.file_name)
        self.client_sock.sendto(pkt, (localhost, self.server_port))
        print("CLIENT sent file request.")
        file_data = bytearray()

        ackd_pkts = []
        while True:
            # Receive 256 Bytes + 10 Bytes (Header) of data from server.
            data = self.client_sock.recv(256+10)

            if data == b'EOF' or not data:
                break

            # Extracting data from packet.
            handler_port = int.from_bytes(data[:2], 'big')
            dest_port = int.from_bytes(data[2:4], 'big')
            msg_len = int.from_bytes(data[4:6], 'big')
            checksum = int.from_bytes(data[6:8], 'big')
            pkt_seq = int.from_bytes(data[8:10], 'big')

            # If the data is invalid, ignore it.
            if not validate_checksum(data):
                continue

            print("Receiving", pkt_seq)
            if pkt_seq == current_seq:
                ack_pkt = create_ack_packet(pkt_seq)
                if random.random() < 0.95:
                    self.client_sock.sendto(ack_pkt, (localhost, handler_port))
                    print("Sending ack", pkt_seq)
                    #  check with window size
                    current_seq += 1
                    ackd_pkts.append(data[10:])

            else:
                if current_seq > 0:
                    ack_pkt = create_ack_packet(current_seq-1)
                    if random.random() < 0.95:
                        self.client_sock.sendto(ack_pkt, (localhost, handler_port))
                        print("Sending ack", current_seq-1)

            for s in ackd_pkts:
                file_data.extend(s)
            ackd_pkts.clear()

        with open(os.path.realpath(self.file_name), 'wb') as file:
            file.write(file_data)

        self.client_sock.close()

    def start_recv(self):
        self.method()


if __name__ == '__main__':
    
    client = Client(sys.argv[1], sys.argv[2])
    client.start_recv()
