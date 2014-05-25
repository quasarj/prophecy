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

    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.init_gui()
        self.init_vim()

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

    def init_vim(self):
        self.vim = neovim.connect('/tmp/neovim')

    def listen_for_message(self):
        while True:
            try:
                self.handle_message(self.vim.next_event())
            except Exception as e:
                print "Vim has disconnected! Shutting down!"
                print e
                QtGui.QApplication.quit()

    def handle_message(self, message):
        print "New message: {}".format(message)
        mtype, args = message

        if mtype == 'query':
            db, first, last = args

            query = ' '.join(self.vim.buffers[0][first - 1:last])

            print db
            print first, last
            print query

            self.execute_signal.emit(db, query)

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

def showWindow():
    app = QtGui.QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    showWindow()
