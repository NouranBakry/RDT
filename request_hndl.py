from threading import Thread
from window import Window
import socket
import Packet
import time
from select import select
import math
import random

TIMEOUT = 0.05


class RequestHandler(Thread):

    seq_size = 0

    def __init__(self, file, conn, method, args):
        Thread.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # When binding a socket to port 0, the underlying kernel will bind the socket to any free port available to app.
        self.sock.bind(('192.168.1.3', 0))
        # Here we get the IP and PORT number that the OS reserved for the socket.
        self.addr, self.port = self.sock.getsockname()
        self.dest_addr = conn
        # [10:] since the first 10 bytes are headers
        self.file_requested = file[10:].decode('utf8')

        self.window_size, self.seed, self.loss_prob = args

        if method in ["RDT", "rdt"]:
            self.method = self.rdt30
        elif method in ["SR", "sr"]:
            self.method = self.selective_repeat
        elif method in ["GBN", "gbn"]:
            self.method = self.GBN
        else:
            raise RuntimeError
        
        random.seed(self.seed)

    def udt_send(self, seq_no, data):
        if random.random() > self.loss_prob:
            pkt = Packet.create_udp_packet(self.port, self.dest_addr[1], seq_no, data)
            self.sock.sendto(pkt, self.dest_addr)

    def rdt30(self):

        seq_no = 0
        self.sock.settimeout(0.05)

        with open('serverfiles\\' + self.file_requested, 'rb') as f:
            
            # Chunks the file into 256 Bytes, Note that the packet size is chunk_size + 10 bytes.
            line = f.read(256)

            while line != b'':
                
                # SEND PACKET AND MOVE TO STATE 2
                self.udt_send(seq_no, line)
                print("SERVER Sending packet with seq no ", seq_no)

                # STATE 2 STAY HERE TILL ACKED
                while True:
                    try:
                        data = self.sock.recv(8)
                        if int.from_bytes(data, 'big') == seq_no:
                            print("SERVER received ACK", int.from_bytes(data, 'big'))
                            seq_no = seq_no ^ 1
                            line = f.read(256)
                            break
                        else:
                            continue
                    except socket.timeout:
                        self.udt_send(seq_no, line)

            self.sock.sendto(b'EOF', self.dest_addr)

    def selective_repeat(self):

        window = Window(self.window_size)
        ack = None
        new_ack = False

        with open('serverfiles\\' + self.file_requested, 'rb') as f:
            
            # Calculates the number of required packets to send the file in
            # Advance.
            size = len(f.read())
            f.seek(0)
            packet_num = math.ceil(size / 256)
            
            # Number of sent packets
            sent = 0

            line = f.read(256)

            while sent != packet_num:
                
                # returns 3 lists one for ready sockets to read from, one for
                # ready sockets to send on and one for exceptions.
                ready = select([self.sock], [self.sock], [])

                # Ready to send on sockets
                if ready[1]:

                    # If the next_sequence value is still in the window frame
                    # if this is false, then it means we sent all of the packets
                    # currently in the window and we're waiting for ACKs
                    if window.within_win():
                        if line:
                            pkt = Packet.create_udp_packet(self.port, self.dest_addr[1], window.next_seq(), line)
                            print("SERVER sending packet with seq", window.next_seq())
                            window.send_next_pkt(line)
                            if random.random() > self.loss_prob:
                                self.sock.sendto(pkt, self.dest_addr)
                            line = f.read(256)
                    # Update the window manually if we sent all of the window's
                    # Packets.
                    else:
                        window.update()
                    
                    # If the packets are send but not acked after TIMEOUT time
                    # Send them again with probability of loss.
                    # RESETS TIMER.
                    
                    for s in window.current_s():
                        if s.sent and not s.acked and (time.time() - s.timeout) >= TIMEOUT:
                            pkt = Packet.create_udp_packet(self.port, self.dest_addr[1], s.seq_no, s.data)
                            print("SERVER resending packet with seq", s.seq_no)
                            window.update_timer(s.seq_no)
                            if random.random() > self.loss_prob:
                                self.sock.sendto(pkt, self.dest_addr)
                    
                if ready[0]:
                    ack = self.sock.recv(8)
                    sent += 1
                    ack_no = int.from_bytes(ack, 'big')
                    window.acknowledge(ack_no)

            self.sock.sendto(b'EOF', self.dest_addr)

    def GBN(self):

        window = Window(self.window_size)
        # ack = None
        # new_ack = False
        current_seq = 0
        with open('serverfiles\\' + self.file_requested, 'rb') as f:

            size = len(f.read())
            f.seek(0)
            packet_num = math.ceil(size / 256)
            sent = 0
            line = f.read(256)

            while sent != packet_num:
                ready = select([self.sock], [self.sock], [])
                if ready[1]:
                    if window.within_win():
                        if line:
                            pkt = Packet.create_udp_packet(self.port, self.dest_addr[1], window.next_seq(), line)
                            window.send_next_pkt(line)
                            if random.random() > self.loss_prob:
                                print("SERVER sending packet with seq", window.next_seq()-1)
                                self.sock.sendto(pkt, self.dest_addr)
                                # print("Server sending packet", window.next_seq()-1)
                                print(window.current_s())
                            line = f.read(256)
                    else:
                        window.update()

                    for s in window.current_s():
                        if s.sent and not s.acked and (time.time() - s.timeout) >= TIMEOUT:
                            pkt = Packet.create_udp_packet(self.port, self.dest_addr[1], s.seq_no, s.data)
                            window.update_timer(s.seq_no)
                            if random.random() > self.loss_prob:
                                print("TIMEOUT ", s.seq_no)
                                print("SERVER resending packet with seq", s.seq_no)
                                self.sock.sendto(pkt, self.dest_addr)
                if ready[0]:
                    ack = self.sock.recv(8)
                    ack_no = int.from_bytes(ack, 'big')
                    print("Receiving ack", ack_no)
                    if current_seq == ack_no:
                        window.acknowledge(ack_no)
                        sent += 1
                        current_seq += 1
                        # print("acknowledged", ack_no)
                        print(window.current_s())
            self.sock.sendto(b'EOF', self.dest_addr)

    def run(self):

        self.method()
        self.sock.close()
