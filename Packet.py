import random

rand_gen = random.SystemRandom()

# Creates a datagram with header;
# sport: source port number - 2 bytes
# dport: dest. port number - 2 bytes
# length: Length of the message - 2 bytes
# checksum of the data - 2 bytes
# seqno: sequence number - 2 bytes
# data: rest of the data in the datagram.
def create_udp_packet(sport, dport, seqno, data, corrupt=True):
    ba = bytearray()
    ba.extend(int.to_bytes(sport, 2, 'big'))
    ba.extend(int.to_bytes(dport, 2, 'big'))
    ba.extend(int.to_bytes(10 + len(data), 2, 'big'))
    if type(data) == str:
        bin_data = bytearray(data.encode('utf8'))
    else:
        bin_data = bytearray(data)

    # temp bytearray to be send to calc_checksum method.
    temp = bytearray(ba)
    temp.extend(int.to_bytes(seqno, 2, 'big'))
    temp.extend(bin_data)
    ba.extend(int.to_bytes(calc_checksum(temp), 2, 'big'))
    ba.extend(int.to_bytes(seqno, 2, 'big'))
    if corrupt:
        ba.extend(alter_byte(bin_data))
    else:
        ba.extend(bin_data)
    return ba

# Calculates the checksum for the datagram.
# It calculates the One's complement only, so sum(data) + checksum = 0xFFFF
# (Internet checksum uses 2-bytes for addition)


def calc_checksum(data):
    chksum = 0
    inp = bytearray(data)

    # Internet checksum uses 2-bytes addition so we add 0x00 byte at the end in case of odd number of bytes
    if len(inp) % 2 == 1:
        inp.append(ord('\0'))

    for i in range(0, len(inp), 2):
        data = ((inp[i] << 8) & 0xFF00) | ((inp[i+1]) & 0xFF)
        chksum += data

        # Carry
        if chksum & 0xFFFF0000 > 1:
            chksum = chksum & 0xFFFF
            chksum += 1

    # 1's complement
    chksum = ~chksum & 0xFFFF
    return chksum


def validate_checksum(data):
    ba = bytearray(data)
    total = 0

    if len(ba) % 2 == 1:
        ba.append(ord('\0'))

    for i in range(0, len(ba), 2):
        temp = ((ba[i] << 8) & 0xFF00) | ((ba[i+1]) & 0xFF)
        total += temp
        if total & 0xFFFF0000 > 1:
            total = total & 0xFFFF
            total += 1

    return total == 0xffff

# Creates 8 bytes of seq_no... don't ask.
def create_ack_packet(seq_no):
    return bytearray(int.to_bytes(seq_no, 8, 'big'))


def alter_byte(packet):
    if rand_gen.random() < 0.99:
        return packet

    index = rand_gen.randint(0, len(packet)-1)
    number = rand_gen.randint(1, 255)

    packet[index] = (packet[index]+number) % 255

    return packet
