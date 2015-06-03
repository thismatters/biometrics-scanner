from time import sleep
# from datetime import datetime, timedelta
import matplotlib
matplotlib.use('WXAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from threading import Thread
# from multiprocessing import Manager
import wx
# import serial

from daqthread import DAQThread

myEVT_REDRAW = wx.NewEventType()
EVT_REDRAW = wx.PyEventBinder(myEVT_REDRAW, 1)
myEVT_RESTART = wx.NewEventType()
EVT_RESTART = wx.PyEventBinder(myEVT_RESTART, 1)

class MyFrame(wx.Frame):
    def __init__(self, parent, id):
        wx.Frame.__init__(self,parent, id, 'Biometrics Scanner',
                style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER,
                size=(800, 600))
        self.panel = wx.Panel(self, -1)

        self.fig = Figure((5, 4), 75)
        self.canvas = FigureCanvasWxAgg(self.panel, -1, self.fig)
        # self.scroll_range = 400
        # self.canvas.SetScrollbar(wx.HORIZONTAL, 0, 5,
        #                          self.scroll_range)
        # self.canvas.SetPosition((400,1))
        self.start_stop_button = wx.Button(self.panel, -1, "Start");
        self.Bind(wx.EVT_BUTTON, self.start_stop_action, self.start_stop_button)

        self.mark_time_button = wx.Button(self.panel, -1, "Mark");
        self.Bind(wx.EVT_BUTTON, self.mark_time_action, self.mark_time_button)

        self.subject_name_label = wx.StaticText(self.panel, label="", style=wx.ALIGN_CENTER)

        topBar = wx.BoxSizer(wx.HORIZONTAL)
        topBar.Add(self.start_stop_button, 1, wx.EXPAND)
        topBar.Add(self.subject_name_label, 2, wx.CENTER)
        topBar.Add(self.mark_time_button, 1, wx.EXPAND)

        font = wx.Font(22, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, True)
        aggregates_bar = wx.BoxSizer(wx.VERTICAL)
        bpmPanel = wx.Panel(self.panel, -1)
        self.currentBPM = wx.StaticText(bpmPanel, label='##', style=wx.ALIGN_RIGHT, pos=(10, 10))
        self.currentBPM.SetFont(font)
        wx.StaticText(bpmPanel, label='BPM', style=wx.ALIGN_RIGHT, pos=(150, 10))
        aggregates_bar.Add(bpmPanel, 1, wx.EXPAND)

        edResponsePanel = wx.Panel(self.panel,-1)
        self.currentEDR = wx.StaticText(edResponsePanel, label='##', style=wx.ALIGN_RIGHT, pos=(10,10))
        self.currentEDR.SetFont(font)
        wx.StaticText(edResponsePanel, label='kOhms', style=wx.ALIGN_RIGHT, pos=(150,10))
        aggregates_bar.Add(edResponsePanel, 1, wx.EXPAND)

        mainBar = wx.BoxSizer(wx.HORIZONTAL)
        mainBar.Add(self.canvas, 5, wx.EXPAND)
        mainBar.Add(aggregates_bar, 2, wx.EXPAND)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(topBar, 0, wx.EXPAND)
        sizer.Add(mainBar, 5, wx.EXPAND)

        self.panel.SetSizer(sizer)
        self.panel.Fit()

        # Setting up the menu.
        filemenu = wx.Menu()

        # wx.ID_ABOUT and wx.ID_EXIT are standard IDs provided by wxWidgets.
        about_button = filemenu.Append(wx.ID_ABOUT, "&About"," Information about this program")
        self.Bind(wx.EVT_MENU, self.OnAbout, about_button)

        filemenu.AppendSeparator()
        exit_button = filemenu.Append(wx.ID_EXIT,"E&xit"," Terminate the program")
        self.Bind(wx.EVT_MENU, self.OnExit, exit_button)
        # Creating the menubar.
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.

        # Try at 1 Hz, 2 Hz, and 10 Hz to see if the threading.Timer performs better than the wx.Timer
        # self.redrawTimer = RepeatingTimer(0.5, self.onRedrawTimer)

        # self.redrawTimer = wx.Timer(self)
        # self.Bind(wx.EVT_TIMER, self.onRedrawTimer, self.redrawTimer)
        self.Bind(EVT_REDRAW, self.onRedraw)
        self.Bind(EVT_RESTART, self.onRestart)

        self.mark_times = list()

        self.daqThread = None
        self.running = False

        self.beats_drawn = 0
        self.marks_drawn = 0
        self.init_data()
        self.init_plot()

        # self.canvas.Bind(wx.EVT_SCROLLWIN, self.OnScrollEvt)

    def init_data(self):
        self.t_min = 0

        # Size of plot window:
        self.t_window = 15
        self.t_undrawn = 2

        # Indices of data interval to be plotted:
        self.t_start = 0
        self.t_end = self.t_start + self.t_window

    def init_plot(self):
        self.axes1 = self.fig.add_subplot(3, 1, 1)
        self.axes2 = self.fig.add_subplot(3, 1, 2)
        self.axes3 = self.fig.add_subplot(3, 1, 3)
        self.axes = [self.axes1, self.axes2, self.axes3]

        self.reset_plot()

    def reset_plot(self):
        self.beats_drawn = 0
        self.marks_drawn = 0
        self.axes1.cla()
        self.plot_data1 = \
                  self.axes1.plot(self.t_start, self.t_end)[0]
        self.plot_data_beats = \
                  self.axes1.plot(0, -600, 'ro')[0]
        self.plot_data_marks1 = \
                  self.axes1.plot(0, -600, 'ko')[0]
        self.axes1.set_xlim(self.t_undrawn - self.t_window, self.t_undrawn)
        self.axes1.set_ylim(-512,512)  # for now
        self.axes1.set_ylabel('ECG')

        self.axes2.cla()
        self.plot_data2 = \
                  self.axes2.plot(self.t_start, self.t_end)[0]
        self.plot_data_marks2 = \
                  self.axes2.plot(0, -600, 'ko')[0]
        self.plot_point2 = self.axes2.plot(0,0,'go')[0]
        self.axes2.set_xlim(self.t_undrawn - self.t_window, self.t_undrawn)
        self.axes2.set_ylim(50,100)
        self.axes2.set_ylabel('Pulse rate (BPM)')

        self.axes3.cla()
        self.plot_data3 = \
                  self.axes3.plot(self.t_start, self.t_end)[0]
        self.plot_data_marks3 = \
                  self.axes3.plot(0, -600, 'ko')[0]
        self.plot_point1 = self.axes1.plot(0,-600,'go')[0]
        self.plot_point3 = self.axes3.plot(0,0,'go')[0]
        self.axes3.set_xlim(self.t_undrawn - self.t_window, self.t_undrawn)
        self.axes3.set_ylim(100,800)
        self.axes3.set_ylabel('EDR (kOhms)')

        self.canvas.draw()
        self.backgrounds = [self.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]


    def onRedraw(self, event):
        last_drawable = self.daqThread.last_drawable
        first_drawable = self.daqThread.first_drawable
        if last_drawable is None:
            return
        self.currentBPM.SetLabel('%0.3f' % self.daqThread.bpm2[last_drawable])
        if self.daqThread.pulse_regular:
            self.currentBPM.SetForegroundColour((0,255,0))
        else:
            self.currentBPM.SetForegroundColour((255,0,0))

        self.currentEDR.SetLabel('%0.3f' % self.daqThread.edr[last_drawable])

        self.t_max = self.daqThread.t[last_drawable]
        if self.t_max + self.t_undrawn < self.t_window:
            self.t_start = 0
            self.t_end = self.t_window
            # Pop a sample from the front of the array?
            # If so, store the values in a master list that doesn't lose data
        else:
            self.t_end = self.t_max + self.t_undrawn
            self.t_start = self.t_end - self.t_window

        i = len(self.daqThread.beats)
        beats_list = list()
        beats_list_y = list()
        while i > 0 and (self.daqThread.beats[i-1] - self.t_max > self.t_undrawn - self.t_window):
            beats_list.append(self.daqThread.beats[i-1] - self.t_max)
            beats_list_y.append(1)
            i -= 1

        i = len(self.daqThread.marks)
        marks_list = list()
        marks_list_y = list()
        while i > 0 and (self.daqThread.marks[i-1] - self.t_max > self.t_undrawn - self.t_window):
            marks_list.append(self.daqThread.marks[i-1] - self.t_max)
            marks_list_y.append(1)
            i -= 1

        # Update data in plot:
        self.canvas.restore_region(self.backgrounds[0])
        self.plot_data1.set_xdata([x - self.t_max for x in self.daqThread.t[first_drawable:last_drawable]])
        self.plot_data1.set_ydata(self.daqThread.ecg[first_drawable:last_drawable])
        # self.plot_point1.set_xdata(self.daqThread.t[last_drawable])
        self.plot_point1.set_ydata(self.daqThread.ecg[last_drawable])
        self.plot_data_beats.set_xdata(beats_list);
        self.plot_data_beats.set_ydata([x * 200 for x in beats_list_y]);
        self.plot_data_marks1.set_xdata(marks_list);
        self.plot_data_marks1.set_ydata([x * -200 for x in marks_list_y]);
        self.axes1.draw_artist(self.plot_data_marks1)
        self.axes1.draw_artist(self.plot_data1)
        self.axes1.draw_artist(self.plot_data_beats)
        self.axes1.draw_artist(self.plot_point1)
        self.canvas.blit(self.axes1.bbox)

        self.canvas.restore_region(self.backgrounds[1])
        self.plot_data2.set_xdata([x - self.t_max for x in self.daqThread.t[first_drawable:last_drawable]])
        self.plot_data2.set_ydata(self.daqThread.bpm2[first_drawable:last_drawable])
        # self.plot_point2.set_xdata(self.daqThread.t[last_drawable])
        self.plot_point2.set_ydata(self.daqThread.bpm2[last_drawable])
        self.plot_data_marks2.set_xdata(marks_list);
        self.plot_data_marks2.set_ydata([x * 80 for x in marks_list_y]);
        self.axes1.draw_artist(self.plot_data_marks2)
        self.axes2.draw_artist(self.plot_data2)
        self.axes2.draw_artist(self.plot_point2)
        self.canvas.blit(self.axes2.bbox)

        self.canvas.restore_region(self.backgrounds[2])
        self.plot_data3.set_xdata([x - self.t_max for x in self.daqThread.t[first_drawable:last_drawable]])
        self.plot_data3.set_ydata(self.daqThread.edr[first_drawable:last_drawable])
        # self.plot_point3.set_xdata(self.daqThread.t[last_drawable])
        self.plot_point3.set_ydata(self.daqThread.edr[last_drawable])
        self.plot_data_marks3.set_xdata(marks_list);
        self.plot_data_marks3.set_ydata([x * 700 for x in marks_list_y]);
        self.axes1.draw_artist(self.plot_data_marks3)
        self.axes3.draw_artist(self.plot_data3)
        self.axes3.draw_artist(self.plot_point3)
        self.canvas.blit(self.axes3.bbox)



        # while self.beats_drawn < len(self.daqThread.beats):
        #     beat_time = self.daqThread.beats[self.beats_drawn]
        #     self.axes1.plot([beat_time, beat_time], [-512,512], 'g')
        #     # self.axes2.plot([beat_time, beat_time], [100,800], 'g')
        #     self.beats_drawn += 1
        #     self.axes1.text(beat_time, -400, '%d' % self.beats_drawn)
        #     # self.axes2.text(beat_time, 125, '%d' % self.beats_drawn)

        while self.marks_drawn < len(self.daqThread.marks):
            mark_time = self.daqThread.marks[self.marks_drawn]
            self.axes1.plot([mark_time, mark_time], [-512,512], 'r')
            self.axes2.plot([mark_time, mark_time], [50,100], 'r')
            self.axes3.plot([mark_time, mark_time], [100,800], 'r')
            self.marks_drawn += 1
            self.axes1.text(mark_time, -400, '%d' % self.marks_drawn)
            self.axes2.text(mark_time, 55, '%d' % self.marks_drawn)
            self.axes3.text(mark_time, 125, '%d' % self.marks_drawn)

        # Redraw:
        # self.canvas.draw()

    # def OnScrollEvt(self, event):
    #     # Update the indices of the plot:
    #     self.t_start = self.t_min + event.GetPosition()/self.scroll_range * self.t_max
    #     self.i_end = self.t_min + self.t_window + event.GetPosition()/self.scroll_range * self.t_max
    #     self.draw_plot()

    def OnAbout(self, event):
        """"""

    def onRestart(self, event):
        if self.running:
            redrawThread = RedrawThread(self)
            redrawThread.start()

    def start_stop_action(self, event):
        if self.running:
            self.start_stop_button.SetLabel("Processing...")
            self.running = False
            self.daqThread.stop()
            while self.daqThread.is_alive():
                sleep(0.1)
            self.daqThread = None
            self.start_stop_button.SetLabel("Start")
        else:
            self.reset_plot()
            self.running = True
            self.daqThread = DAQThread()
            self.daqThread.t_drawable = self.t_window - self.t_undrawn
            self.daqThread.start()
            redrawThread = RedrawThread(self)
            redrawThread.start()
            self.start_stop_button.SetLabel("Stop")

        # if self.redrawTimer.IsRunning():
        #     self.redrawTimer.Stop()
        #     self.daqThread.stop()
        #     while self.daqThread.is_alive():
        #         sleep(0.1)
        #     self.daqThread = None
        #     # consider plotting all the data and saving it for posterity!
        #     self.start_stop_button.SetLabel("Start")
        # else:
        #     self.reset_plot()

        #     self.daqThread = DAQThread()
        #     self.daqThread.start()
        #     # confirmed to work at 1 Hz on Rpi v2.
        #     self.redrawTimer.Start(1000)
        #     # self.daqThread.startime'] = datetime.utcnow()

        #     self.start_stop_button.SetLabel("Stop")


    def OnExit(self, event):
        exit()

    def mark_time_action(self, event):
        if self.daqThread.is_alive():
            self.daqThread.add_mark()


class RedrawThread(Thread):
    def __init__(self, parent):
        ''''''
        super(RedrawThread, self).__init__()
        self._parent = parent

    def run(self):
        redraw_evt = wx.PyCommandEvent(myEVT_REDRAW, -1)
        wx.PostEvent(self._parent, redraw_evt)
        # Wait a little bit??
        sleep(0.3)
        # Throw event that will cause this thread to restart!
        restart_evt = wx.PyCommandEvent(myEVT_RESTART, -1)
        wx.PostEvent(self._parent, restart_evt)


class MyApp(wx.App):
    def __init__(self):
        wx.App.__init__(self)

    def OnInit(self):
        self.frame = MyFrame(parent=None,id=-1)
        self.frame.Show()
        self.SetTopWindow(self.frame)
        return True

if __name__ == '__main__':
    # manager = Manager()

    # plot_data = manager.dict()
    # plot_data = {'t': list(), 'ecg': list(), 'edr': list(), 'start_time': None, 'beats': list(), 'bpm': None}  # consider using a Manager object for this

    app = MyApp()
    app.MainLoop()
