#!/usr/bin/env python
""" ZMQ command utility

    Takes command output and publishes it to a ZeroMQ socket,
    or subscribes to output and sends to stdout.

    Example:
      Publisher: 
        ./zmq_cmd.py --zmq tcp://127.0.0.1:1234 --pub 'tail -f /var/log/system.log'
      
      Subscriber: 
        ./zmq_cmd.py --zmq tcp://127.0.0.1:1234 --sub

"""
import argparse
import os
import pty
import sys
import time
import zmq

OUTPUT_TOPIC = "O"

def zmq_publish_command(command, zmq_addr):
    """ Executes command and sends output to ZeroMQ PUB socket with zmq_addr
        A pseudo-terminal is used so commands expecting a "real" terminal can still be run. 
    """
    (pid, fd) = pty.fork()
    if not pid:
        # child (slave)
        rc = os.system(command)
        sys.exit(rc)
    else:
        ctx = zmq.Context()
        sock = ctx.socket(zmq.PUB)
        sock.bind(zmq_addr)
        
        # parent (master)
        done = False
        while not done:
            data = os.read(fd, 8192)
            if data:
                sock.send("%s %s" % (OUTPUT_TOPIC, data))
            else:
                done = True
        sock.send("%s " % (OUTPUT_TOPIC)) # no data: signals end of output
        sock.close()
        ctx.term()

def zmq_subscribe_output(zmq_addr, fd_out=sys.stdout.fileno()):
    """ Subscribe and print output from zmq_addr 
    """
    # TODO: First message sent by publisher is always dropped?
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, OUTPUT_TOPIC)
    sock.connect(zmq_addr)
    fout = os.fdopen(fd_out, 'w')
    done = False

    while not done:
        data = sock.recv()
        topic, message = data.split(" ", 1)
        if topic == OUTPUT_TOPIC:
            if message == '':
                done = True
            else:
                os.write(fd_out, message)   
                fout.flush()
            
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Publish or Subscribe command output to/from a ZeroMQ socket')
    parser.add_argument('--zmq', dest='zmq', action='store',
                        help='ZeroMQ address to bind/connect to. Example: tcp://127.0.0.1:1234')
    parser.add_argument('--pub', dest='command', action='store',
                        help='Publish: command to run')
    parser.add_argument('--sub', dest='sub', action='store_true',
                        help='Subscribe: display output from socket')
    args = parser.parse_args()

    if args.zmq is None or (args.command is None and not args.sub) or (args.command is not None and args.sub):
        parser.print_help()
        sys.exit(1)
  
    if args.command: 
        zmq_publish_command(args.command, args.zmq)
    else:
        zmq_subscribe_output(args.zmq)
