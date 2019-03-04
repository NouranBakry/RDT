from collections import OrderedDict
from recordclass import recordclass
import time


class WinObj(recordclass('WinObj', ('seq_no', 'sent', 'acked', 'data', 'timeout'))):

    def __str__(self):
        return str(self.seq_no)

    def __repr__(self):
        return self.__str__()


class Window:
    def __init__(self, size, bits=16):

        self.next_sequence = 0
        self.base_sequence = 0
        self.max_window_size = 2 ** bits
        self.window_size = size
        self.window = []
        self._init_window()

    def _init_window(self):
        for _ in range(self.max_window_size):
            self.window.append(WinObj(_, False, False, None, None))

    def __contains__(self, seqno):
        return seqno < self.base_sequence + self.window_size and seqno >= self.base_sequence

    ###############################################
    #
    # SERVER METHODS
    #
    ###############################################

    def within_win(self):
        return self.next_sequence < self.base_sequence + self.window_size and \
                self.next_sequence >= self.base_sequence

    def next_seq(self):
        return self.next_sequence

    def send_next_pkt(self, data):
        self.window[self.next_sequence].sent = True
        self.window[self.next_sequence].data = data
        self.window[self.next_sequence].timeout = time.time()
        self.next_sequence = (self.next_sequence + 1) % self.max_window_size

    def acknowledge(self, seq):
        if seq > self.max_window_size:
            raise RuntimeError
        self.window[seq].acked = True
        self._advance_window()

    def update(self):
        self._advance_window()

    def current_s(self):
        start = self.base_sequence
        end = (self.base_sequence + self.window_size) % self.max_window_size

        if end < start:
            return self.window[start:] + self.window[:end]

        return self.window[start:end]

    def update_timer(self, seq):
        self.window[seq].timeout = time.time()

    ###############################################
    #
    # CLIENT METHODS
    #
    ###############################################

    def buffer_data(self, data, seq):
        self.window[seq].acked = True
        self.window[seq].data = data

    def update_base(self):
        self.window[self.base_sequence] = WinObj(self.base_sequence, False, False, None, None)
        self.base_sequence = (self.base_sequence + 1) % self.max_window_size

    def current_c(self):
        start = self.base_sequence
        end = (self.base_sequence+self.window_size) % self.max_window_size

        # Circular slicing, if end is less than start the list will return
        # Empty.

        if end < start:
            return self.window[start:] + self.window[:end]

        return self.window[start:end]

    ###############################################
    #
    # GENERAL / PRIVATE METHODS
    #
    ###############################################
    
    def print_current_window(self):
        for i in range(self.base_sequence, self.base_sequence+self.window_size):
            print(self.window[i % self.max_window_size])

    def _advance_window(self):
        for i in range(self.base_sequence, self.base_sequence+self.window_size):
            if self.window[i % self.max_window_size].acked:
                self.base_sequence = (self.base_sequence + 1) % self.max_window_size
                self.window[i % self.max_window_size] = WinObj(i % self.max_window_size, False, False, None, None)
            else:
                break