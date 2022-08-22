from io import open
from packet import Packet
import threading
import argparse
import socket

DEBUG = 0

sock = None
thread_lock = threading.Lock()

seqnum_exp = 0  # Expecting seqnum
buffer = []


if __name__ == '__main__':
    # Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("<Host name of emulator>")
    parser.add_argument("<Emulator receiving port number>", help="UDP port number used by the emulator to receive ACKs from the receiver")
    parser.add_argument("<Receiver receiving port number>", help="UDP port number used by the receiver to receive data from the emulator")
    parser.add_argument("<File>", help="name of the file into which the received data is written")
    args = parser.parse_args()

    args = args.__dict__
    emu_addr = str(args["<Host name of emulator>"])
    emu_port = int(args["<Emulator receiving port number>"])
    receive_port = int(args["<Receiver receiving port number>"])
    file_name = str(args["<File>"])

    # Clear the file content
    file = open(file_name, "w")
    file.close()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', receive_port))
    # stop = False
    while True:
        message, addr = sock.recvfrom(1024)
        packet = Packet(message)
        if packet.seqnum == seqnum_exp:
            if packet.typ == 2:
                if DEBUG == 1: print("Received EOT, send EOT")
                eot_packet = Packet(2, 0, 0, '')
                sock.sendto(eot_packet.encode(), (emu_addr, emu_port))
                sock.close()
                break
            else:
                if DEBUG == 1: print("Received packet: %s" % packet.seqnum)
                with open(file_name, "a") as f:
                    f.write(packet.data)
                    f.close()
                seqnum_exp += 1
                stop = False
                while not stop:
                    found = False
                    for p in buffer:
                        if p.seqnum == seqnum_exp:
                            found = True
                            with open(file_name, "a") as f:
                                f.write(p.data)
                                f.close()
                            buffer.remove(p)
                            seqnum_exp += 1
                            stop = True
                    if not found:
                        stop = True
                ack_packet = Packet(0, seqnum_exp - 1, 0, '')
                sock.sendto(ack_packet.encode(), (emu_addr, emu_port))
                if DEBUG == 1: print("Send ACK: %s" % (seqnum_exp - 1))
        else:
            if seqnum_exp < packet.seqnum <= seqnum_exp + 10:
                if DEBUG == 1: print("Received packet buffer: %s" % packet.seqnum)
                # check if packet already in buffer
                found = False
                for p in buffer:
                    if p.seqnum == packet.seqnum:
                        found = True
                        break
                if not found:
                    buffer.append(packet)
            ack_packet = Packet(0, seqnum_exp - 1, 0, '')
            sock.sendto(ack_packet.encode(), (emu_addr, emu_port))
            if DEBUG == 1: print("Send ACK 2: %s" % (seqnum_exp - 1))

