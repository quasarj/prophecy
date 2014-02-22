import vim
import sys
import threading
import time
from PyQt4 import Qt, QtGui, QtCore

from aoc.db.databases import default_connection


window = None
app = None

class Window(QtGui.QWidget):

    pop_signal = QtCore.pyqtSignal(object, object)
    execute_signal = QtCore.pyqtSignal(object, object)
    processing_signal = QtCore.pyqtSignal(bool)

    conn = None
    cur = None
    database = None
    data = None

    scroll_pause = False

    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.table = QtGui.QTableWidget(1, 1, self)
        self.table.verticalHeader().setDefaultSectionSize(19)
        self.table.setAlternatingRowColors(True)

        # self.buttonSave = QtGui.QPushButton('Save', self)
        # self.buttonSave.clicked.connect(self.handleSave)

        # self.buttonMore = QtGui.QPushButton('More', self)
        # self.buttonMore.clicked.connect(self.get_more)
        self.messageLabel = QtGui.QLabel(self)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.table)

        layout.addWidget(self.messageLabel)

        # layout.addWidget(self.buttonMore)
        # layout.addWidget(self.buttonSave)

        self.pop_signal.connect(self.populate)
        self.execute_signal.connect(self.execute)
        self.processing_signal.connect(self.set_processing)

        self.table.verticalScrollBar().valueChanged.connect(self.scroll)

    def set_processing(self, state):
        """Show processing message and hide table, or reverse of that"""
        if state:
            self.table.hide()
            self.messageLabel.show()
            self.messageLabel.setText("Processing query...")
        else:
            self.table.show()
            self.messageLabel.hide()


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

        self.cur = self.conn.cursor()

        self.cur.execute(query)

        headers = [i[0] for i in self.cur.description]
        
        data = self.cur.fetchmany(50)

        #populate, but on the GUI thread
        self.pop_signal.emit(data, headers)

        self.scroll_pause = False
        self.processing_signal.emit(False) # show the table

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

    def append(self):
        for row in self.data:
            vim.current.buffer.append(','.join([str(i) for i in row]))

def showWindow():
    global window, app

    app = QtGui.QApplication(sys.argv)
    window = Window()
    # window.resize(640, 480)
    window.show()
    # sys.exit(app.exec_())
    app.exec_()

    # when the qt app ends, get rid of the window
    del app
    del window
    window = None


def run_sql(cmdline, from_line, to_line):
    global window

    # break the commandline up here
    database = cmdline

    from_line = int(from_line) - 1  # buffer is 0-index
    to_line = int(to_line)          # however, to_line reports one less

    query = '\n'.join(vim.current.buffer[from_line:to_line]).replace(';', '')

    if not window:
        t = threading.Thread(target=showWindow) #, args=(data, headers))
        # t.daemon = True
        t.start()
        
        # wait for the window to appear. TODO: there must be a better way
        for i in xrange(1000):
            if window: break
            time.sleep(0.1)

    # window.pop_signal(data, headers)
    # window.pop_signal.emit(data, headers)
    window.execute_signal.emit(database, query)

    vim.command("return 1") # return from the vim function?


def close_sql():
    global app, window

    try:
        if app:
            app.quit()
            del app
            app = None

        if window:
            del window
            window = None

    except: pass


