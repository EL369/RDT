import socket

ports = []

while(len(ports) < 5):
    for i in range(7):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        addr = s.getsockname()
        ports.append(addr[1])
        s.close()
    ports = list(set(ports))

print(ports)

host1="localhost"
host2="localhost"
host3="localhost"

output_file = 'output.txt'
input_file = 'input.txt'

max_delay = 1 #In millisecs
discard_prob = 0.3
verbose_mode = 1 #Boolean:Setto1,thenetworkemulatorwilloutputitsinternalprocessing).
print("nEmulator "+
      str(ports[1])+" "+
      host2+" "+
      str(ports[4])+" "+
      str(ports[3])+" "+
      host3+" "+
      str(ports[2])+" "+
      str(max_delay)+" "+
      str(discard_prob)+" "+
      str(verbose_mode))

print("receiver "+
      host1+" "+
      str(ports[3])+" "+
      str(ports[4])+" "+
      output_file)

sender_wait = 50 ##Milliseconds
print("sender "+
      host1+" "+
      str(ports[1])+" "+
      str(ports[2])+" "+
      str(sender_wait)+" "+
      input_file)