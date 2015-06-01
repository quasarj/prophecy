#!/usr/bin/env python2

import sys
import threading
import time
import json
import logging

from dateutil import parser
from PyQt5 import Qt, QtGui, QtCore, QtWidgets
from neovim import attach
import cx_Oracle

from aoc.db.connections import DefaultConnection
from aoc.util.log import config_logging

import queries
config_logging(filename="vim-prophecy.log",
               screen_level="INFO",
               file_level="DEBUG")
log = logging.getLogger()

window = None
app = None

entries = {}


def parse_var_magic(vars):
    """Check each variable for the 'magic' string

    If found, convert to the data type specified, if possible.
    """
    ret = []
    for var in vars:
        var = str(var)
        if var.startswith('~date: '):
            _, date = var.split(': ')
            var = convert_to_date(date)
        elif var.startswith('~number: '):
            _, num = var.split(': ')
            var = float(num)

        ret.append(var)

    log.debug("Final parsed vars:")
    log.debug(ret)
    return ret


def convert_to_date(string):
    """Attempt to parse the given string using several different
    formats before giving up"""

    try:
        return parser.parse(string)
    except:
        pass

    raise RuntimeError("Failed to parse your date string: {}. "
                       "I tried as hard as I could!".format(string))


class VariableEntryDialog(QtWidgets.QDialog):
    def __init__(self, parent, variables, defaults=None):  # , data, headers):
        QtWidgets.QWidget.__init__(self, parent)

        layout = QtWidgets.QVBoxLayout(self)
        self.inputs = []

        if defaults:
            defaults = dict(zip(variables, defaults))

        for v in variables:
            h = QtWidgets.QHBoxLayout()

            label = QtWidgets.QLabel(str(v), self)
            if defaults:
                edit = QtWidgets.QLineEdit(defaults[v], self)
            else:
                edit = QtWidgets.QLineEdit(self)

            edit.returnPressed.connect(self.onOkayClicked)

            self.inputs.append(edit)

            h.addWidget(label)
            h.addWidget(edit)
            layout.addLayout(h)

        okay = QtWidgets.QPushButton("Okay", self)
        layout.addWidget(okay)

        okay.clicked.connect(self.onOkayClicked)

        self.inputs[0].setFocus()

    def onOkayClicked(self):
        self.result = [i.text() for i in self.inputs]
        self.accept()


class Window(QtWidgets.QWidget):

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
        QtWidgets.QWidget.__init__(self)
        self.init_gui()
        self.init_vim(socket)

        self.describe_verbose = False

        # t = threading.Thread(target=self.listen_to_fifo)
        t = threading.Thread(target=self.listen_for_message)
        t.daemon = True  # ensure the thread dies gracefully at shutdown
        t.start()

    def init_gui(self):
        self.setWindowTitle("Prophecy 0.4")

        self.font = QtGui.QFont()
        # self.font.setPointSize(14)
        self.font.setFamily("Courier New")

        self.table = QtWidgets.QTableWidget(1, 1, self)
        self.table.setFont(self.font)
        self.table.verticalHeader().setDefaultSectionSize(19)
        self.table.setAlternatingRowColors(True)

        self.messageLabel = QtWidgets.QLabel(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table)

        layout.addWidget(self.messageLabel)

        self.pop_signal.connect(self.populate)
        self.execute_signal.connect(self.execute)
        self.processing_signal.connect(self.set_processing)
        self.message_signal.connect(self.set_message)

        self.table.verticalScrollBar().valueChanged.connect(self.scroll)

        self.set_message("Awaiting connection from Vim...")

    def init_vim(self, socket):
        self.vim = attach('socket', path=socket)
        self.vim.vars['vimsql_channel_id'] = self.vim.channel_id
        # notify that we are up and running
        sys.stderr.write("Ready")

        # self.vim_session = socket_session(socket)
        # self.vim = Nvim.from_session(self.vim_session)

    # This is a main function run by a thread!
    def listen_for_message(self):
        while True:
            try:
                self.handle_message(self.vim.session.next_message())
                # self.handle_message(self.vim.next_message())
            except Exception as e:
                log.warn(e)
                log.warn(repr(e))
                log.fatal("Vim has disconnected! Shutting down!")
                QtWidgets.QApplication.quit()
                return

    def handle_message(self, message):
        if message is None:
            return

        # reset some things to defaults
        self.describe_verbose = False

        log.debug("New message: {}".format(message))
        ntype, mtype, args = message

        message_mapping = {'query': self.handle_query,
                           'insertquery': self.handle_insertquery,
                           'describe_simple': self.handle_describe_simple,
                           'describe_verbose': self.handle_describe_verbose,
                           'explain': self.handle_explain}
        try:
            message_mapping[mtype](args)
        except KeyError:
            self.message_signal.emit(
                "Did not understand message from vim: {}".format(message))

    def handle_query(self, args):
        db, query = self.parse_query_args(args)
        self.execute_signal.emit(db, query)

    def parse_query_args(self, args):
        db, first, last = args[0]

        if first == last:
            first, last = detect_query(self.vim, first)
        else:
            first -= 1

        query = '\n'.join(self.vim.current.buffer[first:last])

        log.debug(db)
        log.debug("{} {}".format(first, last))
        log.debug(query)

        return (db, query)

    def handle_explain(self, args):
        database, query = self.parse_query_args(args)

        self.connect_to_database(database)

        query = "explain plan for " + query

        self.scroll_pause = True
        self.processing_signal.emit(True)  # hide the table
        self.describe_verbose = True

        # this must be run directly
        log.debug("Starting explain plan...")
        try:
            self.cur.execute(query)
        except Exception as e:
            self.message_signal.emit("Error: {}".format(e))
            return

        self.execute_signal.emit(
            database,
            "select * from "
            "table(dbms_xplan.display('PLAN_TABLE', NULL, 'ALL'))")

    def handle_describe_simple(self, args):
        database, object = args[0]
        self.connect_to_database(database)
        if '.' in object:
            owner, object = object.split('.')
        else:
            owner = None

        query = queries.describe_simple

        binds = ['NAME', 'OWNER']
        vars = [object, owner]

        self.scroll_pause = True
        self.processing_signal.emit(True)  # hide the table
        t = threading.Thread(target=self.run_query,
                             args=(database, query, binds, vars))
        t.start()

    def handle_describe_verbose(self, args):
        database, object = args[0]
        self.connect_to_database(database)
        object = object.upper()
        if '.' in object:
            owner, object = object.split('.')
        else:
            owner = None

        query = queries.describe_verbose.format(owner, object)

        self.scroll_pause = True
        self.processing_signal.emit(True)  # hide the table
        self.describe_verbose = True

        # this must be run directly
        log.debug("Starting verbose describe..")
        try:
            self.cur.callproc("dbms_output.enable", parameters=['1000000'])
            self.cur.execute(query)

        except Exception as e:
            self.message_signal.emit("Error: {}".format(e))
            return

        statusVar = self.cur.var(cx_Oracle.NUMBER)
        lineVar = self.cur.var(cx_Oracle.STRING)
        output = []
        while True:
            self.cur.callproc("dbms_output.get_line", (lineVar, statusVar))
            if statusVar.getvalue() != 0:
                break
            output.append((lineVar.getvalue(), ''))

        headers = ['DBMS_OUTPUT', '']

        # populate, but on the GUI thread
        self.pop_signal.emit(output, headers)
        self.processing_signal.emit(False)  # show the table
        self.scroll_pause = False

    def handle_insertquery(self, args):
        db, first, last = args[0]  # message comes wrapped in a list
        log.debug("insertquery was requested")

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
        log.info(message)
        self.table.hide()
        self.messageLabel.setText(message)
        self.messageLabel.show()

    def scroll(self, val):
        if not self.scroll_pause:
            max = self.table.verticalScrollBar().maximum()
            if val >= max:  # user has scrolled to the end
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

        for i, row in enumerate(data):
            for j, field in enumerate(row):
                self.add_item(i, j, field)

        self.table.resizeColumnsToContents()

    def execute(self, database, query):
        global entries

        # it is here that we must detect that variables need to be bound
        self.connect_to_database(database)
        binds = None
        vars = None

        self.cur.prepare(query)
        binds = self.cur.bindnames()

        if binds:
            defaults = [entries.get(i, '') for i in binds]
            win = VariableEntryDialog(self, binds, defaults)
            win.exec_()
            vars = win.result

            # merge new values into history
            entries.update(dict(zip(binds, vars)))

        try:
            if vars:
                vars = parse_var_magic(vars)
            self.scroll_pause = True
            self.processing_signal.emit(True)  # hide the table
            t = threading.Thread(target=self.run_query,
                                 args=(database, query, binds, vars))
            t.start()
        except Exception as e:
            self.message_signal.emit("Error: {}".format(e))

    def connect_to_database(self, database):
        # reuse existing DB connection if this is for the same DB
        if self.database != database:
            if self.conn:
                    self.conn.close()
            self.conn = DefaultConnection(database)
            self.database = database

        # auto re-connect if disconnected
        try:
            self.conn.ping()
        except:
            self.conn = DefaultConnection(database)

        self.cur = self.conn.cursor()

    # This is a main function run by a thread!
    def run_query(self, database, query, binds, vars):
        if binds and vars:
            params = dict(zip(binds, vars))
        else:
            params = None

        log.debug("Executing query:")
        log.debug(query)
        log.debug("Params: {}".format(params))
        try:
            if params is None:
                self.cur.execute(query)
            else:
                self.cur.execute(query, params)

        except Exception as e:
            self.message_signal.emit("Error: {}".format(e))
            return

        if self.cur.description:
            headers = [i[0] for i in self.cur.description]
            data = self.cur.fetchmany(50)

            # populate, but on the GUI thread
            self.pop_signal.emit(data, headers)

            self.processing_signal.emit(False)  # show the table
        else:  # if this was not a select query
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

            for i, row in enumerate(data):
                for j, field in enumerate(row):
                    self.add_item(current + i, j, field)

    def add_item(self, x, y, value):
        # log.debug("adding item: {}".format(str(repr(value))))
        color = None
        if value is None:
            if not self.describe_verbose:
                value = "{null}"
                color = (242, 255, 188, 255)
            else:
                value = ""

        item = QtWidgets.QTableWidgetItem(str(value))
        item.setFont(self.font)
        if color:
            item.setBackground(QtGui.QBrush(QtGui.QColor(*color)))
        self.table.setItem(x, y, item)


def detect_query(vim, line_number):
    """Figure out where the query begins and ends"""

    start = line_number - 1  # zero index
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
    app = QtWidgets.QApplication(sys.argv)
    window = Window(socket)
    window.show()
    sys.exit(app.exec_())


def test_variable_entry(data):
    app = QtWidgets.QApplication(sys.argv)
    window = VariableEntryDialog(None, data)
    window.exec_()
    print window.result
    sys.exit()


if __name__ == "__main__":
    try:
        showWindow(sys.argv[1])
    except Exception as e:
        log.warn("Unhandled exception caught in main thread. Details follow.")
        log.warn(e)
        log.warn(repr(e))

    # test_variable_entry(['a', 'b', 'c'])
