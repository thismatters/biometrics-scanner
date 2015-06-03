from time import sleep
# from multiprocessing import Manager

from daqthread import DAQThread

if __name__ == '__main__':
    # manager = Manager()

    # plot_data = manager.dict()
    # plot_data = {'t': list(), 'ecg': list(), 'edr': list(), 'start_time': None, 'beats': list(), 'bpm': None}  # consider using a Manager object for this

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
