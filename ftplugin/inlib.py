#!/usr/bin/env python2

import sys
import json

class NoMoreMessages(Exception):
    pass

terminator = '|'
buffer = []
def get_messages(callback):
    global buffer, terminator

    while True:
        data = sys.stdin.read(1)  # this blocks
        if len(data) == 0: break  # exit if stdin has been closed

        if terminator in data:
            s = ''.join(buffer)
            message = None
            try:
                message = json.loads(s)
            except:
                print "Received message, but it wasn't JSON: {}".format(s)

            if message is not None:
                callback(message)
            buffer = []

            continue

        buffer.append(data)

    raise NoMoreMessages("stdin was closed!")
