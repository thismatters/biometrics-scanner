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
        self.thresh_f_list = list()
        self.t = list()
        self.ecg = list()
        self.edr = list()
        self.bpm1 = list()
        self.bpm2 = list()
        self.name_to_list = {'time': self.t, 'ecg': self.ecg, 'edr': self.edr, 
                             'bpm1': self.bpm1, 'bpm2': self.bpm2}
        self.beats = list()
        self.beat_type = list()
        self.marks = list()
        self.first_drawable = 0
        self.t_drawable = 12
        self.last_drawable = None
        self.start_time = None
        self.samples = None
        self.pulse_found = False
        self.pulse_regular = False
        self.ser = serial.Serial(port='/dev/ttyAMA0', 
                                 baudrate=115200, 
                                 timeout=1)
        self.ser.close()
        self.debug = False

    def gather_sample(self):
        prefix = None
        value = None
        if self.ser.isOpen():
            try:
                line = self.ser.readline()
            except:
                print 'bad readline()'
            if self.debug:
                print "Prefix: %s, value: %d" % (prefix, value)
            if line:
                try:
                    prefix = line[0]
                    value = long(line[1:])
                except ValueError as e:
                    print "line: %s" % (line, )
        return prefix, value

    def run(self):
        appendix = {'S': self.t, 'K': self.ecg, 'G': self.edr, 
                    'F': self.hp, 'Q': self.sqr, 'I': self.integrated, 
                    'B': self.beats, 'P': self.bpm2, 'O': self.bpm1, 
                    'T': self.thresh_i_list, 'Y': self.thresh_f_list,
                    'W': self.beat_type}
        
        appendage = lambda x: 
            {'S': x, 'K': x, 'G': x * 220 / (1024 - x), 'F': x, 'Q': x, 
             'I': x, 'B': self.t[-1] + (x - self.samples) * 0.005, 
             'P': 60000.0 / x, 'O': 60000.0 / x, 'T': x, 'Y': x, 'W': x}
        
        while self.keep_running:
            prefix, value = gather_sample()

            if prefix is None or value is None:
                continue
            if prefix is 'S':
                if self.samples is None:
                    value = 0
                    self.start_time = datetime.utcnow()
                else:
                    value = self.t[-1] + (value - self.samples) * 0.005
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
                        print "Arduino reset happened!"
                        self.samples -= value


    def stop(self):
        self.ser.close()
        self.keep_running = False
        plt.clf()

        fig, axes = plt.subplots(nrows=6)
        y_data = [(self.edr, ), 
                  (self.bpm1, self.bpm2),
                  (self.ecg, ),
                  (self.hp, self.thresh_f_list, [x * 0.5 for x in self.thresh_f_list]),
                  (self.sqr, ),
                  (self.integrated, self.thresh_i_list, [x * 0.5 for x in self.thresh_i_list])]
        styles = [('b', ),
                  ('b','r'),
                  ('b', ),
                  ('b', 'r', 'g'),
                  ('b', ),
                  ('b', 'r', 'g')] 
        draw_marks = [True, True, False, False, False, False]
        draw_beats = [False, False, True, False, False, False]
        y_labels = ['EDR [kOhm]', 'Pulse [bpm]', 'ECG', 'Filtered', 'D and squared', 'Integrated']

        for ax, data_tup, style_tup, draw_mark, draw_beat, y_label in zip(
                axes, y_data, styles, draw_marks, draw_beats, y_labels):
            y_min = 100000
            y_max = 0
            for data, style in zip (data_tup, style_tup):
                ax.plot(self.t[:last_drawable], data[:last_drawable], style)
                y_max = max(y_max, max(data[:last_drawable]))
                y_min = min(y_min, min(data[:last_drawable]))
            if draw_mark:
                for i in range(0, len(self.marks)):
                    time = self.marks[i]
                    ax.plot([time,time], [y_min,y_max], 'g')
                    ax.text(time, y_min + (y_max - y_min) * 0.75, '%d' % (i + 1, ))
            if draw_beat:
                for (time, _type) in zip(self.beats, self.beat_type):
                    ax.plot([time,time], [y_min,y_max], 'g')
                    ax.text(time, y_min + (y_max - y_min) * 0.25, '%d' % _type)
            ax.set_ylabel(ylabel)

        default_size = plt.gcf().get_size_inches()
        plt.gcf().set_size_inches((0.5 * self.t[-1], 8))
        plt.savefig('trial_run_at_%s.png' % self.start_time)
        # plt.savefig('trial_run.png')

        print "Average sample time: %f" % (float(self.t[-1]) / len(self.t),)

    def add_mark(self):
        self.marks.append(timedelta.total_seconds(datetime.utcnow() - self.start_time))

    def get_drawable(self, data_set_name=None):
        ret_val = None
        try:
            ret_val = self.name_to_list[data_set_name][self.first_drawable:self.last_drawable]
        except KeyError as e:
            print "(get_drawable) No data set by name: %s" % str(data_set_name)
            ret_val = [0,0]
        except IndexError as e:
            print "(get_drawable) Bad range."
            ret_val = [0,0]
        return ret_val

    def get_last(self, data_set_name=None):
        ret_val = None
        try:
            ret_val = self.name_to_list[data_set_name][last_drawable]
        except KeyError as e:
            print "(get_drawable) No data set by name: %s" % str(data_set_name)
            ret_val = 0
        except IndexError as e:
            print "(get_drawable) Bad range."
            ret_val = 0
        return ret_val


