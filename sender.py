from packet import Packet
import time
import threading
import argparse
import socket
import logging

DEBUG = 0

sock = None
lock = threading.Lock()
timer_lock = threading.Lock()

emu_addr = None  # Host address of emulator
emu_port = None  # Emulator receiving port number
receive_port = None  # Sender receiving port number
timeout = None  # Timeout interval in units of millisecond
file_name = None  # File to be transferred

window_size = 1  # num of packets been sent but not yet acked and packets not yet sent
packets_sent_not_acked = []  # packets sent yet tobe acked
packets = []  # All packets
last_ack = None  # seqnum of the last acked packet received
num_duplicate_acks = 0

start_time = 0
current_time = 0
timer_running = False
timer_thread_running = True

timestamp = 0
formatter = logging.Formatter('%(message)s')
seqnum_log = None
ack_log = None
N_log = None


def setup_logger(name, log_file, level=logging.INFO):
    handler = logging.FileHandler(log_file, mode="w")
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


def timerStop():
    global timer_running
    if DEBUG == 1: print("timer stopped")
    timer_running = False


def timerStart():
    timer_lock.acquire()
    global timer_running
    global start_time
    timer_running = True
    start_time = time.time() * 1000
    timer_lock.release()


def readFile():
    global packets
    i = 0
    with open(file_name) as f:
        while True:
            c = f.read(500)
            if c == '':
                break
            p = Packet(1, i, len(c), c)  # not mod 32, output (seqnum % 32) for the logs
            packets.append(p)
            if DEBUG == 1: print("Add packet %s" % i)
            i += 1


def sendPacket():
    global timestamp
    global timer_thread_running
    i = 0
    N_log.info("t=%s %s" % (timestamp, window_size))
    stop = False
    while not stop:
        lock.acquire()
        if i >= len(packets):
            if last_ack == packets[-1].seqnum and len(packets_sent_not_acked) == 0:
                if DEBUG == 1: print("Sending EOT")
                eot_packet = Packet(2, i, 0, '')
                sock.sendto(eot_packet.encode(), (emu_addr, emu_port))
                timestamp += 1
                seqnum_log.info("t=%s %s" % (timestamp, "EOT"))
                timerStop()
                stop = True
                timer_thread_running = False
                # break
        elif len(packets_sent_not_acked) < window_size:
            if DEBUG == 1: print("Sending packet: %s" % i)
            if len(packets_sent_not_acked) == 0:  # Start timer for oldest transmitted but not yet acked packet
                timerStart()
            timestamp += 1
            seqnum_log.info("t=%s %s" % (timestamp, packets[i].seqnum % 32))
            sock.sendto(packets[i].encode(), (emu_addr, emu_port))
            packets_sent_not_acked.append(packets[i])
            i += 1
        lock.release()


def receiveAck():
    global last_ack
    global window_size
    global num_duplicate_acks
    global timestamp
    global timer_thread_running
    sock.bind(('', receive_port))
    stop = False
    while not stop:
        message, addr = sock.recvfrom(1024)
        ack_packet = Packet(message)
        lock.acquire()
        timestamp += 1
        if ack_packet.typ == 0:  # received ACK
            if DEBUG == 1: print("Received ACK %s" % ack_packet.seqnum)
            ack_log.info("t=%s %s" % (timestamp, ack_packet.seqnum % 32))
            # new ACK
            if (last_ack is None) or (ack_packet.seqnum > last_ack):
                if DEBUG == 1: print("Update packets_sent_not_acked %s, %s" % (len(packets_sent_not_acked), last_ack))
                remove_list = []
                for packet in packets_sent_not_acked:
                    if packet.seqnum <= ack_packet.seqnum:
                        remove_list.append(packet)
                for p in remove_list:
                    packets_sent_not_acked.remove(p)
                last_ack = ack_packet.seqnum
                if DEBUG == 1: print("Update: %s, %s" % (len(packets_sent_not_acked), last_ack))
                num_duplicate_acks = 0
                if window_size < 10:
                    window_size += 1
                    N_log.info("t=%s %s" % (timestamp, window_size))
                # If there are transmitted but yet tobe acknowledged packets, the timer is restarted
                if len(packets_sent_not_acked) > 0:
                    timerStart()
                # If there are no outstanding packets, the timer is stopped
                else:
                    timerStop()
            # duplicate ACK
            elif ack_packet.seqnum == last_ack:
                num_duplicate_acks += 1
                if DEBUG == 1: print("Duplicate ACK %s" % num_duplicate_acks)
                if num_duplicate_acks == 3 and packets_sent_not_acked[0].seqnum == last_ack + 1:
                    window_size = 1
                    sock.sendto(packets_sent_not_acked[0].encode(), (emu_addr, emu_port))
                    timerStart()

                    N_log.info("t=%s %s" % (timestamp, window_size))
                    seqnum_log.info("t=%s %s" % (timestamp, packets_sent_not_acked[0].seqnum % 32))
                    num_duplicate_acks = 0
        else:  # received EOT
            if DEBUG == 1: print("Received EOT")
            ack_log.info("t=%s %s" % (timestamp, "EOT"))
            if DEBUG == 1: print("%s %s %s" % (last_ack, packets[-1].seqnum, len(packets_sent_not_acked)))
            sock.close()
            stop = True
        lock.release()


def timer():
    global current_time
    global window_size
    global timestamp
    while True:
        if not timer_thread_running:
            if DEBUG == 1: print("Timer Stop")
            break
        if timer_running:
            timer_lock.acquire()
            current_time = time.time() * 1000 - start_time
            timer_lock.release()
            # If a timeout occurs, the sender sets N=1 and retransmits the packet that caused the timer to timeout
            lock.acquire()
            if current_time >= timeout and len(packets_sent_not_acked) > 0:
                if DEBUG == 1: print("Timeout %s" % current_time)
                window_size = 1
                sock.sendto(packets_sent_not_acked[0].encode(), (emu_addr, emu_port))
                if DEBUG == 1: print("Resend packet %s" % packets_sent_not_acked[0].seqnum)
                timerStart()
                timestamp += 1
                N_log.info("t=%s %s" % (timestamp, window_size))
                seqnum_log.info("t=%s %s" % (timestamp, packets_sent_not_acked[0].seqnum % 32))

            lock.release()


if __name__ == '__main__':
    # Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("<Host address of emulator>")
    parser.add_argument("<Emulator receiving port number>",
                        help="UDP port number used by the emulator to receive data from the sender")
    parser.add_argument("<Sender receiving port number>",
                        help="UDP port number used by the sender to receive ACKs from the emulator")
    parser.add_argument("<Timeout interval>", help="in units of millisecond")
    parser.add_argument("<File>", help="name of the file to be transferred")
    args = parser.parse_args()

    args = args.__dict__
    emu_addr = str(args["<Host address of emulator>"])
    emu_port = int(args["<Emulator receiving port number>"])
    receive_port = int(args["<Sender receiving port number>"])
    timeout = int(args["<Timeout interval>"])
    file_name = str(args["<File>"])

    readFile()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seqnum_log = setup_logger("seqnum", "seqnum.log")
    ack_log = setup_logger("ack", "ack.log")
    N_log = setup_logger("N", "N.log")

    # start one thread for sending, one for receiving, and one for timer
    sendThread = threading.Thread(target=sendPacket)#, args=(,))
    receiveThread = threading.Thread(target=receiveAck)
    timerThread = threading.Thread(target=timer)
    sendThread.start()
    receiveThread.start()
    timerThread.start()

    sendThread.join()
    if DEBUG == 1: print("send thread killed")
    timerThread.join()
    if DEBUG == 1: print("timer thread killed")
    receiveThread.join()
    if DEBUG == 1: print("receive thread killed")
