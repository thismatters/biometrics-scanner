from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threading import Thread
import serial

class DAQThread(Thread):
    def __init__(self):
        super(DAQThread, self).__init__()
        self.hp = list()  # results of the hi-pass filter
        self.sqr = list() # results of the squaring
        self.integrated = list() # results of the integration
        self.thresh_i_list = list()
        self.thresh1_f_list = list()
        self.thresh2_f_list = list()
        self.t = list()
        self.ecg = list()
        self.edr = list()
        self.bpm1 = list()
        self.bpm2 = list()
        self.maxs = {'K': -1000, 'G': -1000, 'P': -1000, 'O': -1000}
        self.mins = {'K': 10000, 'G': 10000, 'P': 10000, 'O': 10000}
        self.name_to_list = {'time': self.t, 'ecg': self.ecg, 'edr': self.edr,
                             'bpm1': self.bpm1, 'bpm2': self.bpm2}
        self.name_to_prefix = {'ecg': 'K', 'edr': 'G',
                             'bpm1': 'P', 'bpm2': 'O'}
        self.beats = list()
        self.beat_type = list()
        self.marks = list()
        self.t_current = 0
        self.first_drawable = 0
        self.last_drawable = None
        self._first_drawable = 0
        self._last_drawable = None
        self.t_drawable = 12
        self.start_time = None
        self.samples = 0
        self.pulse_found = False
        self.pulse_regular = False
        self._lock = False
        self.keep_running = True
        self.silent = False
        self._plot_all_data = False

        self.ser = serial.Serial(port='/dev/ttyAMA0',  # This should maybe be an initialization variable?
                                 baudrate=115200,
                                 timeout=1)
        self.ser.close()
        self.debug = False

    def gather_sample(self):
        '''Actually reads the serial data from the buffer, splits, and
            returns the prefix and value of the line.'''
        prefix = None
        value = None
        if self.ser.isOpen():
            line = None
            try:
                line = self.ser.readline()
            except:
                if not self.silent:
                    print 'bad readline()'
            if line:
                try:
                    prefix = line[0]
                    value = long(line[1:])
                except ValueError as e:
                    if not self.silent:
                        print "line: %s" % (line, )
        return prefix, value

    def run(self):
        '''Processes and catalogs the incoming data.'''
        self.ser.open()
        appendix = {'S': self.t, 'K': self.ecg, 'G': self.edr,
                    'F': self.hp, 'Q': self.sqr, 'I': self.integrated,
                    'B': self.beats, 'P': self.bpm2, 'O': self.bpm1,
                    'T': self.thresh_i_list, 'Y': self.thresh1_f_list,
                    'W': self.beat_type, 'H': self.thresh2_f_list}

        appendage = lambda x: {
            'S': x, 'K': x, 'G': (x * 220 / (1024 - x) if x < 1024 else -1), 'F': x, 'Q': x,
            'I': x, 'B': self.t_current + (x - self.samples) * 0.005,
            'P': ((60000.0 / x) if x != 0 else -1),
            'O': ((60000.0 / x) if x != 0 else -1),
            'T': x, 'Y': x, 'W': x, 'H': x}

        while self.keep_running:
            prefix, value = self.gather_sample()

            if prefix is None or value is None:
                continue
            if prefix is 'S':
                if not self.t:
                    self.samples = value
                    value = 0
                    self.start_time = datetime.utcnow()
                else:
                    self.t_current = float(self.t[-1] + float(value - self.samples) / 200)
                    self.samples = value
                    value = self.t_current
                    if self.debug and not self.silent:
                        print 'time: %f' % (value, )
                    if self.last_drawable is None:
                        self.last_drawable = 0
                        self.first_drawable = 0
                    else:
                        self.last_drawable += 1
                    if self.t[self.first_drawable] < self.t[self.last_drawable] - self.t_drawable:
                        self.first_drawable += 1

            if self.samples is not None or prefix is 'S':
                try:
                    appendix[prefix].append(appendage(value)[prefix])
                except KeyError as e:
                    if prefix is 'N':
                        if value:
                            self.pulse_regular = True
                        else:
                            self.pulse_regular = False
                    if prefix is 'R':  # reset counter
                        if not self.silent:
                            print "Arduino reset happened!"
                        self.samples -= value

            if prefix in self.maxs:
                test_value = appendage(value)[prefix]
                if test_value > self.maxs[prefix]:
                    self.maxs[prefix] = test_value
                if test_value < self.mins[prefix]:
                    self.mins[prefix] = test_value


    def stop(self):
        '''Closes the data stream and plots the data'''
        self.ser.close()
        self.keep_running = False
        plt.clf()

        y_data = [(self.edr, ), (self.bpm1, self.bpm2), (self.ecg, )]
        styles = [('b', ), ('b','r'), ('b', )]
        if self._plot_all_data:
            y_data.extend([(self.hp, self.thresh1_f_list, self.thresh2_f_list),
                           (self.sqr, ),
                           (self.integrated, self.thresh_i_list, [x * 0.5 for x in self.thresh_i_list])])
            styles.extend([('b', 'r', 'g'),
                           ('b', ),
                           ('b', 'r', 'g')])
        fig, axes = plt.subplots(nrows=len(y_data))
        draw_marks = [True, True, False, False, False, False]
        draw_beats = [False, False, True, False, False, False]
        y_labels = ['EDR [kOhm]', 'Pulse [bpm]', 'ECG', 'Filtered', 'D and squared', 'Integrated']
        units = ['kOhm', 'bpm', 'V', 'na', 'na', 'na']

        if self.debug and not self.silent:
            print 'time:'
            print str(self.t)
        if not self.silent:
            print str([self.t[x] for x in self.marks])
        for ax, data_tup, style_tup, draw_mark, draw_beat, y_label, unit in zip(
                axes, y_data, styles, draw_marks, draw_beats, y_labels, units):
            y_min = 100000
            y_max = 0
            for data, style in zip (data_tup, style_tup):
                if self.debug and not self.silent:
                    print 'preparing plot for %s' % (y_label)
                    print str(data)
                try:
                    ax.plot(self.t[:self.last_drawable], data[:self.last_drawable], style)
                except ValueError:
                    if not self.silent:
                        print 'Plotting failed for %s' % (y_label)
                y_max = max(y_max, max(data[:self.last_drawable]))
                y_min = min(y_min, min(data[:self.last_drawable]))
            if draw_mark:
                for i in range(0, len(self.marks)):
                    time = self.t[self.marks[i]]
                    ax.plot([time,time], [y_min,y_max], 'g')
                    ax.text(time, y_min + (y_max - y_min) * 0.9, '%d' % (i + 1, ))
                    ax.text(time, y_min + (y_max - y_min) * 0.1, '%.1f %s' % (data_tup[0][self.marks[i]], unit) )
            if draw_beat:
                for (time, _type) in zip(self.beats, self.beat_type):
                    ax.plot([time,time], [y_min,y_max], 'g')
                    ax.text(time, y_min + (y_max - y_min) * 0.95, '%d' % _type)
            ax.set_ylabel(y_label)

        plt.gcf().set_size_inches((min(32, 0.5 * self.t[-1]), 8))
        # plt.savefig('trial_run_at_%s.png' % self.start_time)
        plt.savefig('trial_run.png')
        if not self.silent:
            print "Average sample time: %f" % (float(self.t[-1]) / len(self.t),)

    def add_mark(self):
        '''Adds a mark to the data stream'''
        self.marks.append(self.last_drawable)

    def get_drawable(self, data_set_name=None):
        '''Returns the portion of the requested data set that is
            presently visible in the GUI'''
        ret_val = None
        last_drawable = self.last_drawable
        first_drawable = self.first_drawable
        if self._lock:
            last_drawable = self._last_drawable
            first_drawable = self._first_drawable
        try:
            ret_val = self.name_to_list[data_set_name][first_drawable:last_drawable]
        except KeyError as e:
            if not self.silent:
                print "(get_drawable) No data set by name: %s" % str(data_set_name)
            ret_val = [0,0]
        except IndexError as e:
            if not self.silent:
                print "(get_drawable) Bad range."
            ret_val = [0,0]
        except TypeError:
            ''''''
        return ret_val

    def get_last(self, data_set_name=None):
        '''Returns the last sample from the usable portion of the
            requested data set'''
        ret_val = None
        last_drawable = self.last_drawable
        if self._lock:
            last_drawable = self._last_drawable
        try:
            ret_val = self.name_to_list[data_set_name][last_drawable]
        except KeyError as e:
            if not self.silent:
                print "(get_last) No data set by name: %s" % str(data_set_name)
            ret_val = 0
        except IndexError as e:
            if not self.silent:
                print "(get_last) Bad range."
            ret_val = 0
        except TypeError:
            ''''''
        return ret_val

    def redraw_lock(self):
        '''permits syncronization'''
        self._lock = True
        self._last_drawable = self.last_drawable
        self._first_drawable = self.first_drawable

    def redraw_lock_release(self):
        self._lock = False

    def get_y_limits(self, data_set_name=None):
        ret_val = None
        if data_set_name in self.name_to_prefix:
            prefix = self.name_to_prefix[data_set_name]
            offset = float((self.maxs[prefix] - self.mins[prefix]) / 8.0)
            ret_val = (self.mins[prefix] - offset, self.maxs[prefix] + offset)
        return ret_val

    def plot_all_data(self, value=True):
        '''Sets the application to produce a plot showing all of
        the data collected from the Arduino, this is useful for
        ensuring that the Arduino (and the algorithm) are working
        properly. The default plot just shows the pulse rate and
        the electro-dermal response'''
        self._plot_all_data = value

    def be_quiet(self):
        self.silent = True

    def mark_count(self):
        return len(self.marks)