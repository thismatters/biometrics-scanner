from time import sleep

from daqthread import DAQThread

if __name__ == '__main__':
    run_duration = 6
    print 'Starting'
    daqProcess = DAQThread()
    daqProcess.start()

    minute_count = 0

    while minute_count < run_duration:
        sleep(60)
        daqProcess.add_mark()
        minute_count += 1
        print 'Minute: %d of %d' % (minute_count, run_duration)

    print 'Stopping'
    daqProcess.stop()
    print 'Exiting'
