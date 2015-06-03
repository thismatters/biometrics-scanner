from time import sleep
import matplotlib
matplotlib.use('WXAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from threading import Thread
import wx

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

        self.init_plot()
        
        self.canvas = FigureCanvasWxAgg(self.panel, -1, self.fig)

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

        self.Bind(EVT_REDRAW, self.onRedraw)
        self.Bind(EVT_RESTART, self.onRestart)

        self.mark_times = list()

        self.daqThread = None
        self.running = False

        self.beats_drawn = 0
        self.marks_drawn = 0
        

    def init_plot(self):
        self.t_window = 15
        self.t_undrawn = 2
        self.data_sets = ['ecg', 'bpm2', 'edr'] 
        self.data_limits = [(-512, 512), (50, 120), (100, 800)]
        self.lines = list()
        self.data_labels = ['ECG', 'Pulse Rate (BPM)', 'EDR (kOhms)'] 
        self.show_beats = [True, False, False]
        self.show_marks = [True, True, True]
        self.axes = [self.fig.add_subplot(len(self.data_sets), 1, x) for x in range(0, len(self.data_sets))]
        
        self.reset_plot()

    def reset_plot(self):
        self.beats_drawn = 0
        self.marks_drawn = 0

        for ax, data_label, data_limit, show_beat, show_mark in zip(
                self.axes, self.data_labels, self.data_limits, self.show_beats, self.show_marks):
            ax.cla()
            ax.set_ylabel(data_label)
            data_set_line = ax.plot(0,0)[0]
            data_point_line = ax.plot(0,-600,'go')[0]
            beat_line = None
            mark_line = None
            if show_beat:
                beat_line = ax.plot(0,-600, 'ro')[0]
            if mark_line:
                mark_line = ax.plot(0,-600, 'ko')[0]
            ax.set_xlim(self.t_undrawn - self.t_window, self.t_undrawn)
            ax.set_ylim(*data_limit)
            self.lines.append((data_set_line, data_point_line beat_line, mark_line))

        self.canvas.draw()
        self.backgrounds = [self.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]


    def onRedraw(self, event):
        # last_drawable = self.daqThread.last_drawable
        # first_drawable = self.daqThread.first_drawable
        if last_drawable is None:
            return
        self.currentBPM.SetLabel('%0.3f' % self.daqThread.get_last('bpm2'))
        if self.daqThread.pulse_regular:
            self.currentBPM.SetForegroundColour((0,255,0))
        else:
            self.currentBPM.SetForegroundColour((255,0,0))

        self.currentEDR.SetLabel('%0.3f' % self.daqThread.get_last('edr'))

        t_max = self.daqThread.get_last('time')
        drawable_time = [x - t_max for x in self.daqThread.get_drawable('time')]

        t_cutoff = self.t_undrawn - self.t_window + t_max
        beats_list_x, beats_list_y = zip(
            *[(x, 1) for x in self.daqThread.beats if x > t_cutoff])
        marks_list_x, marks_list_y = zip(
            *[(x, 1) for x in self.daqThread.marks if x > t_cutoff])

        for ax, background, data_set, data_label, data_limit, line_tuple in zip(
                self.axes, self.backgrounds self.data_sets, self.data_labels, self.data_limits, self.lines):
            self.canvas.restore_region(background)
            data_set_line, data_point_line, beat_line, mark_line = line_tuple
            data_set_line.set_xdata(drawable_time)
            data_set_line.set_ydata(self.daqThread.get_drawable(data_set))
            ax.draw_artist(data_set_line)
            data_point_line.set_ydata(self.daqThread.get_last(data_set))
            ax.draw_artist(data_point_line)
            if beat_line is not None:
                beat_line.set_xdata(beats_list_x);
                beat_line.set_ydata([y * (data_limit[1] - (data_limit[1] - data_limit[0]) * 0.125) for y in beats_list_y]);
                ax.draw_artist(beat_line)
            if mark_line is not None:
                mark_line.set_xdata(marks_list_x)
                mark_line.set_ydata([y * (data_limit[0] + (data_limit[1] - data_limit[0]) * 0.125) for y in marks_list_y]);
                ax.draw_artist(mark_line)
            self.canvas.blit(ax.bbox)


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
        sleep(0.3)
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
    app = MyApp()
    app.MainLoop()
