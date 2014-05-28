#!/usr/bin/env python2

import sys
import threading
import time
import json
from PyQt4 import Qt, QtGui, QtCore
import neovim

from aoc.db.databases import default_connection

window = None
app = None

class Window(QtGui.QWidget):

    pop_signal = QtCore.pyqtSignal(object, object)
    execute_signal = QtCore.pyqtSignal(object, object)
    processing_signal = QtCore.pyqtSignal(bool)
    message_signal = QtCore.pyqtSignal(object)

    conn = None
    cur = None
    database = None
    data = None

    scroll_pause = False

    def __init__(self, socket):
        QtGui.QWidget.__init__(self)
        self.init_gui()
        self.init_vim(socket)

        # t = threading.Thread(target=self.listen_to_fifo)
        t = threading.Thread(target=self.listen_for_message)
        t.daemon = True # ensure the thread dies gracefully at shutdown
        t.start()

    def init_gui(self):
        self.setWindowTitle("VimSQL 0.2")

        self.table = QtGui.QTableWidget(1, 1, self)
        self.table.verticalHeader().setDefaultSectionSize(19)
        self.table.setAlternatingRowColors(True)

        self.messageLabel = QtGui.QLabel(self)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.table)

        layout.addWidget(self.messageLabel)

        self.pop_signal.connect(self.populate)
        self.execute_signal.connect(self.execute)
        self.processing_signal.connect(self.set_processing)
        self.message_signal.connect(self.set_message)

        self.table.verticalScrollBar().valueChanged.connect(self.scroll)
        
        self.set_message("Awaiting connection from Vim...")

    def init_vim(self, socket):
        self.vim = neovim.connect(socket)

    def listen_for_message(self):
        while True:
            try:
                self.handle_message(self.vim.next_event())
            except Exception as e:
                print "Vim has disconnected! Shutting down!"
                QtGui.QApplication.quit()
                return

    def handle_message(self, message):
        print "New message: {}".format(message)
        mtype, args = message

        if mtype == 'query':
            db, first, last = args

            if first == last:
                first, last = detect_query(self.vim, first)
            else:
                first -= 1

            query = '\n'.join(self.vim.current.buffer[first:last])

            print db
            print first, last
            print query

            self.execute_signal.emit(db, query)

        if mtype == 'insertquery':
            self.handle_insertquery(args)

    def handle_insertquery(self, args):
        db, first, last = args
        print "insertquery was requested"

        tab_size = max(
            [len(i) for i in self.headers]) + 1

        # create a new scratch buffer
        self.vim.command("new")
        self.vim.command("setlocal buftype=nofile")
        self.vim.command("setlocal bufhidden=hide")
        self.vim.command("setlocal noswapfile")
        self.vim.command("setlocal nowrap")
        self.vim.command("setlocal ts={}".format(tab_size))

        self.vim.current.buffer[0] = '\t'.join([str(i) for i in self.headers])

        for row in self.data:
            self.vim.current.buffer.append(
                '\t'.join([str(i) for i in row]))

    def set_processing(self, state):
        """Show processing message and hide table, or reverse of that"""
        if state:
            self.table.hide()
            self.messageLabel.show()
            self.messageLabel.setText("Processing query...")
        else:
            self.table.show()
            self.messageLabel.hide()

    def set_message(self, message):
        """Show a message and hdie the table"""
        self.table.hide()
        self.messageLabel.setText(message)
        self.messageLabel.show()

    def scroll(self, val):
        if not self.scroll_pause:
            max = self.table.verticalScrollBar().maximum()
            if val >= max: # user has scrolled to the end
                self.get_more()


    def populate(self, data, headers):
        self.data = data
        self.headers = headers

        # clear the table
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        if headers is None:
            self.message_signal.emit("{} rows affected.".format(data))
            return
        if len(data) == 0:
            self.message_signal.emit("Query returned no results!")
            return

        # set the real values
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(data[0]))


        # for j,field in enumerate(headers):
        #     item = QtGui.QTableWidgetItem(str(field))
        #     self.table.setHorizontalHeaderItem(j, item)
        # self.table.setHorizontalHeaderLabels(headers)
        self.table.setHorizontalHeaderLabels(headers)

        for i,row in enumerate(data):
            for j,field in enumerate(row):
                self.add_item(i, j, field)


        self.table.resizeColumnsToContents()

    def execute(self, database, query):
        self.scroll_pause = True
        self.processing_signal.emit(True) # hide the table
        t = threading.Thread(target=self.run_query, args=(database, query))
        t.start()


    def run_query(self, database, query):
        # reuse existing DB connection if this is for the same DB
        if self.database != database:
            if self.conn:
                    self.conn.close()
            self.conn = default_connection.get(database)
            self.database = database

        try:
            self.conn.ping()
        except:
            self.conn = default_connection.get(database)

        self.cur = self.conn.cursor()

        try:
            self.cur.execute(query)
        except Exception as e:
            self.message_signal.emit("Error: {}".format(e))
            return

        if self.cur.description:
            headers = [i[0] for i in self.cur.description]
            data = self.cur.fetchmany(50)

            # populate, but on the GUI thread
            self.pop_signal.emit(data, headers)

            self.processing_signal.emit(False) # show the table
        else: # if this was not a select query
            # pass the rows affected instead
            self.pop_signal.emit(self.cur.rowcount, None)


        self.scroll_pause = False

    # this will probably have to be moved to the same
    # thread as run_query? I doubt it'll work like this
    def get_more(self):
        if self.cur:
            
            data = self.cur.fetchmany(50)
            self.data.extend(data)

            current = self.table.rowCount()
            self.table.setRowCount(current + len(data))

            for i,row in enumerate(data):
                for j,field in enumerate(row):
                    self.add_item(current + i, j, field)

    def add_item(self, x, y, value):
        # color = None if x % 2 else (238, 238, 238, 255)
        color = None 
        if value is None:
            value = "{null}"
            color = (242, 255, 188, 255)
        
        item = QtGui.QTableWidgetItem(str(value))
        if color:
            item.setBackgroundColor(QtGui.QColor(*color))
        self.table.setItem(x, y, item)

def detect_query(vim, line_number):
    """Figure out where the query begins and ends"""
    
    start = line_number - 1  #zero index
    end = line_number

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

def showWindow(socket):
    app = QtGui.QApplication(sys.argv)
    window = Window(socket)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    showWindow(sys.argv[1])
