import vim
import json
import subprocess

proc = None

def detect_query(from_line, to_line):
    """Figure out where the query begins and ends"""
    
    start = from_line - 1  #zero index
    end = to_line

    # if the user had the cursor on a ; line, look one up from there
    if start != 0 and vim.current.buffer[start].startswith(';'):
        start -= 1
        end -= 1

    # search backwards until we find a ; in the first position or row 0
    while start > 0:
        if vim.current.buffer[start].startswith(';'):
            break
        start -= 1

    # search forwards until we find a ; or the end of the file
    buff_len = len(vim.current.buffer)
    while end < buff_len:
        if vim.current.buffer[end].startswith(';'):
            break
        end += 1

    # if the start was on a ;, actually start one line down from there
    if start != 0:
        start += 1 

    return (start, end)

def run_sql(cmdline, from_line, to_line):
    global window

    # TODO: break the commandline up here
    database = cmdline

    start = int(from_line)
    end = int(to_line)

    if from_line == to_line:
        # range not given, must detect it now
        start, end = detect_query(start, end)
    else:
        start = start - 1 # zero index

    query = '\n'.join(vim.current.buffer[start:end]).replace(';', '')


    send_execute(database, query)

    vim.command("return 1") # return from the vim function?

def send_execute(database, query):
    global proc
    path = '/home/quasar/.vim/bundle/VimSQL/ftplugin'

    if proc is None:
        proc = subprocess.Popen([path + "/app.py"], stdin=subprocess.PIPE)
        
    message = {
        'type': 'query',
        'database': database,
        'query': query,
    }
    proc.stdin.write(json.dumps(message) + '|')

