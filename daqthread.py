from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threading import Thread
import serial

class DAQThread(Thread):
    def __init__(self):
        super(DAQThread, self).__init__()
        # self.plotData = plotData
        self.hp = list()  # results of the hi-pass filter
        self.sqr = list() # results of the squaring
        self.integrated = list() # results of the integration
        self.thresh1_i_list = list()
        self.thresh2_i_list = list()
        self.thresh1_f_list = list()
        self.thresh2_f_list = list()
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

    def run(self):
        del self.hp[:]
        del self.sqr[:]
        del self.integrated[:]
        del self.thresh1_i_list[:]
        del self.thresh2_i_list[:]
        del self.thresh1_f_list[:]
        del self.thresh2_f_list[:]
        del self.t[:]
        del self.ecg[:]
        del self.edr[:]
        del self.beats[:]
        del self.beat_type[:]
        del self.bpm2[:]
        del self.marks[:]

        self.first_drawable = 0
        self.last_drawable = None
        self.start_time = None
        self.samples = None
        self.pulse_regular = False
        self.pulse_found = False
        self.ser.open()
        self.keep_running = True
        while self.keep_running and self.ser.isOpen():
            try:
                line = self.ser.readline()
            except:
                print 'bad readline()'
            prefix = None
            value = None
            if self.debug:
                print "Prefix: %s, value: %d" % (prefix, value)
            if line:
                try:
                    prefix = line[0]
                    value = long(line[1:])
                except ValueError as e:
                    print "line: %s" % (line, )

            if not self.keep_running or value is None:
                continue
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
                samples_since_last = value - self.samples
                self.beats.append(self.t[-1] + samples_since_last * 0.005)
            if prefix is 'P':
                self.bpm2.append(60000.0 / value)
                self.pulse_found = True
            if prefix is 'O':
                self.bpm1.append(60000.0 / value)
                self.pulse_found = True
            if prefix is 'T':
                self.thresh1_i_list.append(value)
                self.thresh2_i_list.append(value * 0.5)
            if prefix is 'Y':
                self.thresh1_f_list.append(value)
                self.thresh2_f_list.append(value * 0.5)
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
                print "reset happened!"
                self.samples -= value
            if prefix is 'W':
                self.beat_type.append(value)


    def stop(self):
        self.ser.close()
        self.keep_running = False
        plt.clf()

        n = min(len(self.t),
                len(self.ecg),
                len(self.edr),
                len(self.bpm2),
                len(self.bpm1),
                len(self.hp),
                len(self.thresh1_i_list),
                len(self.thresh1_f_list),
                len(self.sqr),
                len(self.integrated))

        plt.subplot(6,1,1)
        plt.plot(self.t[:n],self.edr[:n])
        for i in range(0, len(self.marks)):
            time = self.marks[i]
            plt.plot([time,time], [100,800], 'g')
            plt.text(time, 125, '%d' % (i + 1, ))
        plt.ylabel('EDR [kOhm]')

        plt.subplot(6,1,2)
        plt.plot(self.t[:n],self.bpm2[:n],'b')
        plt.plot(self.t[:n],self.bpm1[:n],'r')
        for i in range(0, len(self.marks)):
            time = self.marks[i]
            plt.plot([time,time], [50,85], 'g')
            plt.text(time, 80, '%d' % (i + 1, ))
        plt.ylabel('Pulse [bpm]')

        plt.subplot(6,1,3)
        plt.plot(self.t[:n],self.ecg[:n])
        for (time, _type) in zip(self.beats, self.beat_type):
            plt.plot([time,time], [-512,512], 'g')
            plt.text(time, -400, '%d' % _type)
        plt.ylabel('ECG')

        plt.subplot(6,1,4)
        plt.plot(self.t[:n],self.hp[:n])
        plt.plot(self.t[:n],self.thresh1_f_list[:n])
        plt.plot(self.t[:n],self.thresh2_f_list[:n])
        plt.ylabel('Filtered')

        plt.subplot(6,1,5)
        plt.plot(self.t[:n],self.sqr[:n])
        plt.ylabel('D and squared')

        plt.subplot(6,1,6)
        plt.plot(self.t[:n],self.integrated[:n])
        plt.plot(self.t[:n],self.thresh1_i_list[:n])
        plt.plot(self.t[:n],self.thresh2_i_list[:n])
        plt.ylabel('integrated')

        default_size = plt.gcf().get_size_inches()
        plt.gcf().set_size_inches((0.5 * self.t[-1], 8))
        plt.savefig('trial_run_at_%s.png' % self.start_time)
        # plt.savefig('trial_run.png')

        print "Average sample time: %f" % (float(self.t[-1]) / len(self.t), )

    def add_mark(self):
        self.marks.append(timedelta.total_seconds(datetime.utcnow() - self.start_time))



