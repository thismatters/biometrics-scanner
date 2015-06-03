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
        self.beats = list()
        self.beat_type = list()
        self.bpm1 = list()
        self.bpm2 = list()
        self.marks = list()
        self.first_drawable = 0
        self.t_drawable = 12
        self.last_drawable = None
        self.start_time = None
        self.samples = None
        self.pulse_found = False
        self.pulse_regular = False
        self.ser = serial.Serial(port='/dev/ttyAMA0', baudrate=115200, timeout=1)
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
        while self.keep_running and self.ser.isOpen():
            prefix, value = gather_sample()

            if prefix is None or value is None:
                continue
            # try making this a dictionary rather than a switch
            if prefix is 'S':
                if self.samples is None:
                    self.t.append(0)
                    self.samples = value
                    self.start_time = datetime.utcnow()
                else:
                    samples_since_last = value - self.samples
                    self.samples = value
                    self.t.append(self.t[-1] + samples_since_last * 0.005)
            if self.samples is None:
                continue
            if prefix is 'K':
                self.ecg.append(value)
            if prefix is 'G':
                self.edr.append(value * 220 / (1024 - value))
            if prefix is 'F':
                self.hp.append(value)
            if prefix is 'Q':
                self.sqr.append(value)
            if prefix is 'I':
                self.integrated.append(value)
            if prefix is 'B':
                self.beats.append(self.t[-1] + (value - self.samples) * 0.005)
            if prefix is 'P':
                self.bpm2.append(60000.0 / value)
            if prefix is 'O':
                self.bpm1.append(60000.0 / value)
            if prefix is 'T':
                self.thresh_i_list.append(value)
            if prefix is 'Y':
                self.thresh_f_list.append(value)
                if self.samples is not None:
                    if self.last_drawable is None:
                        self.last_drawable = 0
                        self.first_drawable = 0
                    else:
                        self.last_drawable += 1
                    if self.t[self.first_drawable] < self.t[self.last_drawable] - self.t_drawable:
                        self.first_drawable += 1

            if prefix is 'N':
                if value:
                    self.pulse_regular = True
                else:
                    self.pulse_regular = False
            if prefix is 'R':  # reset counter
                print "Arduino reset happened!"
                self.samples -= value
            if prefix is 'W':
                if self.beats:
                    self.beat_type.append(value)


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

        print "Average sample time: %f" % (float(self.t[-1]) / len(self.t),
        )

    def add_mark(self):
        self.marks.append(timedelta.total_seconds(datetime.utcnow() - self.start_time))



