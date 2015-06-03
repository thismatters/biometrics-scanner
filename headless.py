from time import sleep

from daqthread import DAQThread

if __name__ == '__main__':

    print 'Starting'
    daqProcess = DAQThread()
    daqProcess.start()

    sleep(10)
    daqProcess.add_mark()
    print '1 / 3'
    sleep(10)
    daqProcess.add_mark()
    print '2 / 3'
    sleep(10)
    print 'Stopping'
    daqProcess.stop()
    print 'Exiting'
