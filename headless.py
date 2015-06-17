from time import sleep

from daqthread import DAQThread
import sys
import termios
import fcntl
import os

def myGetch():
    fd = sys.stdin.fileno()

    oldterm = termios.tcgetattr(fd)
    newattr = termios.tcgetattr(fd)
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, newattr)

    oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

    c = ''
    try:
        while 1:
            try:
                c = sys.stdin.read(1)
                break
            except IOError: pass
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

    return c

def print_instructions():
    print "Press [space] to mark current time on record, press [q] to quit recording"
    return myGetch()

if __name__ == '__main__':
    run_duration = 6
    print 'Starting'
    daqThread = DAQThread()
    daqThread.be_quiet()
    daqThread.start()
    print 'Started'

    while 1:
        keystroke = print_instructions()
        if keystroke == ' ':
            daqThread.redraw_lock()
            daqThread.add_mark()
            print 'Mark %d added at t=%.1f. \nCurrent pulse rate: %.1f BPM, \nCurrent dermal response: %.1f kOhms' % (daqThread.mark_count(), daqThread.get_last('time'), daqThread.get_last('bpm1'), daqThread.get_last('edr'))
            daqThread.redraw_lock_release()
        if keystroke == 'q' or keystroke == 'Q':
            break
    # minute_count = 0
    # try:
    #     while minute_count < run_duration:
    #         sleep(60)
    #         daqThread.add_mark()
    #         minute_count += 1
    #         print 'Minute: %d of %d' % (minute_count, run_duration)
    # except KeyboardInterrupt:
    #     ''''''
    print 'Stopping'
    daqThread.stop()
    print 'Exiting'
    exit()
