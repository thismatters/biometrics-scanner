
/*  Pulse Sensor Amped 1.4    by Joel Murphy and Yury Gitman   http://www.pulsesensor.com
Pan-Tompkins QRS Detection Algorithm implemented by Paul Stiverson http://thismatters.net
----------------------  Notes ----------------------  ----------------------
This code:
1) Blinks an LED to User's Live Heartbeat   PIN 12
2) Fades an LED to User's Live HeartBeat
3) Determines BPM
4) Prints All of the Above to Serial
Read Me:
https://github.com/WorldFamousElectronics/PulseSensor_Amped_Arduino/blob/master/README.md
and
https://github.com/thismatters/biometrics-scanner/blob/master/README.md
 ----------------------       ----------------------  ----------------------
*/

//  Variables
int pulsePin = 0;                 // Pulse Sensor purple wire connected to analog pin 0
int edr_pin = 1;                 // Pulse Sensor purple wire connected to analog pin 0
int blinkPin = 12;                // pin to blink led at each beat

// Volatile Variables, used in the interrupt service routine!
volatile boolean Pulse = false;     // "True" when User's live heartbeat is detected. "False" when not a "live beat".
volatile boolean QS = false;        // becomes true when Arduoino finds a beat.

// Regards Serial OutPut  -- Set This Up to your needs
static boolean serialVisual = false;   // Set to 'false' by Default.  Re-set to 'true' to see Arduino Serial Monitor ASCII Visual Pulse

volatile unsigned long sample_count = 0;          // used to determine pulse timing
volatile unsigned long last_R_sample = 0;           // used to find IBI
volatile int beat_count = 0;
volatile unsigned long reset_diff = 0;
volatile boolean did_reset = false;

// Various buffers for Pan Tompkins
volatile long sample[13];
volatile long low_pass[33];
volatile long high_pass[5];
volatile long diff = 0;
volatile unsigned long squared[30];
volatile unsigned long integrated[2];
volatile int rr_intervals1[8];
volatile int rr_intervals2[8];
volatile int average_RR1 = 950;  // in milliseconds
volatile int average_RR2 = 1000;
volatile long max_slope = 0;
volatile long prior_max_slope = 0;

// Thresholds for Pan Tompkins
volatile boolean was_rising_i = true;
volatile boolean int_is_rising_i;
volatile boolean peak_found_i;
volatile boolean beat_happened_i;
volatile unsigned long peak_val_i;
volatile unsigned long thresh1_i = 30000;
volatile unsigned long thresh2_i = 15000;
volatile unsigned long npk_i =     15000;
volatile unsigned long spk_i =     70000;
volatile unsigned long candidate_peak_index_i = 0;
volatile unsigned long candidate_peak_val_i[2] = {15000, 688};

volatile boolean was_rising_f = true;
volatile boolean int_is_rising_f;
volatile boolean peak_found_f;
volatile boolean beat_happened_f;
volatile long peak_val_f;
volatile long thresh1_f = 1375;
volatile long thresh2_f = 688;
volatile long npk_f =     2500;
volatile long spk_f =     1000;
volatile unsigned long candidate_peak_index_f = 0;
volatile unsigned long candidate_peak_val_f[2] = {15000, 688};

volatile int peak_type =-1;
volatile int intervals_skipped = 0;

void interruptSetup(){
    // The Pan Tompkins Algorithm utilizes a 200Hz sampling rate
    // Initializes Timer1 to throw an interrupt every 5mS.
    // The Gertboard has a 12Mhz clock.
    TCCR1A = 0x00; // DISABLE OUTPUTS AND PWM ON DIGITAL PINS 9 & 10
    TCCR1B = 0x0A; // GO INTO 'CTC' MODE, PRESCALE = 8
    TCCR1C = 0x00; // DON'T FORCE COMPARE
    OCR1AH = 0x1D; // first bit of the top count
    OCR1AL = 0x4C; // second bit of the top count (OCR1A = 0x1D4C = 7500)
    TIMSK1 = 0x02; // enable output compare A match (OCIE1A)
    sei();         // MAKE SURE GLOBAL INTERRUPTS ARE ENABLED
}


// THIS IS THE TIMER 1 INTERRUPT SERVICE ROUTINE.
// Timer 1 makes sure that we take a reading every 5 miliseconds
ISR(TIMER1_COMPA_vect){                         
    cli();       // disable interrupts while we do this
    int_is_rising_i = false;
    peak_found_i = false;
    beat_happened_i = false;
    int_is_rising_f = false;
    peak_found_f = false;
    beat_happened_f = false;

    roll_array_l(sample, 13, (long) analogRead(pulsePin) - 512);   // read the Pulse Sensor
    sample_count++;

    roll_array_l(low_pass, 33, (long) 2*low_pass[0]-low_pass[1]+sample[0]-2*sample[6]+sample[12]);
    roll_array_l(high_pass, 5, (long) high_pass[0]+low_pass[16]-low_pass[17]+(low_pass[32]-low_pass[0])/32);
    diff = 2 * high_pass[0] + high_pass[1] - high_pass[3] - 2 * high_pass[4];
    roll_array_ul(squared, 30, (unsigned long) (diff*diff)/64);

    if (squared[0] > max_slope) {
        max_slope = squared[0];
    }

    unsigned long long sum = 0;
    for (int i=29; i>=0; i--){
        sum += squared[i];
    }
    unsigned long quotient = (unsigned long) (sum / 30);
    integrated[1] = integrated[0];
    integrated[0] = quotient;

    // look for peaks in 'high_pass'
    if ((long) high_pass[0] >= (long) high_pass[1]) {
        int_is_rising_f = true;
    }
    if ((was_rising_f == true && int_is_rising_f == false) &&  (((long) high_pass[1] > 0 && (long) high_pass[0] > 0) && (long) high_pass[2] > 0) ) {
        if (sample_count > 60) {
            peak_found_f = true;
            peak_val_f = high_pass[1];
        }
    }

    if (peak_found_f == true) {
        if (peak_val_f >= thresh1_f) {
            spk_f = (peak_val_f + 7*spk_f)/8;
            beat_happened_f = true;
        } else {
            npk_f = (peak_val_f + 7*npk_f)/8;
            if (peak_val_f > candidate_peak_val_f[1]) {
                candidate_peak_val_f[0] = integrated[1];
                candidate_peak_val_f[1] = peak_val_f;
                candidate_peak_index_f = sample_count;
            }
        }
        thresh1_f = npk_f + (spk_f - npk_f) / 2;
        thresh2_f = npk_f;
    }

    // look for peaks in 'integrated'
    if (integrated[0] >= integrated[1]) {
        int_is_rising_i = true;
    }
    if (was_rising_i == true && int_is_rising_i == false) {
        if (sample_count > 60) {
            peak_found_i = true;
            peak_val_i = integrated[1];
        }
    }

    // identify peak and update thresholds
    if (peak_found_i == true) {
        // There is a minimum 200ms refractory period between beats (200 / 5 = 40 thus wait 40 samples before accepting a new peak)
        if (peak_val_i >= thresh1_i){
            spk_i = (peak_val_i + 7*spk_i)/8;
            beat_happened_i = true;
        } else {
            npk_i = (peak_val_i + 7*npk_i)/8;
            if (peak_val_i > candidate_peak_val_i[0]) {
                candidate_peak_val_i[0] = peak_val_i;
                candidate_peak_val_i[1] = high_pass[1];
                candidate_peak_index_i = sample_count;
            }
        }
        thresh1_i = npk_i + (spk_i - npk_i) / 4;
        thresh2_i = thresh1_i / 2;
    }

    if (sample_count > last_R_sample + 40) {
        if (sample_count < last_R_sample + 72 && max_slope < prior_max_slope / 2) {
            beat_happened_i = false;
            beat_happened_f = false;
        }
        if ((beat_happened_f == true && integrated[0] > thresh1_i) || (beat_happened_i == true && high_pass[0] > thresh1_f)) {
            beat_happened(sample_count,0);
            candidate_peak_index_i = 0;
            candidate_peak_val_i[0] = thresh2_i;
            candidate_peak_val_i[1] = 0;
            candidate_peak_index_f = 0;
            candidate_peak_val_f[0] = 0;
            candidate_peak_val_f[1] = thresh2_f;
        }
    }

    if ((sample_count - last_R_sample) * 500 > (unsigned long) 166 * average_RR2) {
        // look back at largest peak between thresh1_i and thresh2_i
        if (candidate_peak_index_f != 0 && candidate_peak_index_i != 0) {
            int candidate_peak_offset = candidate_peak_index_i - candidate_peak_index_f;
            if (candidate_peak_offset * candidate_peak_offset < 100) {
                beat_happened((candidate_peak_index_i + candidate_peak_index_f) / 2,1);
                spk_i = (candidate_peak_val_i[0] + 3*spk_i)/4;
                thresh1_i = npk_i + (spk_i - npk_i) / 4;
                thresh2_i = thresh1_i / 2;
                candidate_peak_index_i = 0;
                candidate_peak_val_i[0] = thresh2_i;
                candidate_peak_val_i[1] = 0;

                spk_f = (candidate_peak_val_f[1] + 3*spk_f)/4;
                thresh1_f = npk_f + (spk_f - npk_f) / 2;
                thresh2_f = npk_f;
                candidate_peak_index_f = 0;
                candidate_peak_val_f[0] = 0;
                candidate_peak_val_f[1] = thresh2_f;
            }

        } else {
            if (candidate_peak_index_i != 0 && candidate_peak_val_i[1] > thresh2_f) {
                beat_happened(candidate_peak_index_i,2);
                spk_i = (candidate_peak_val_i[0] + 3*spk_i)/4;
                thresh1_i = npk_i + (spk_i - npk_i) / 4;
                thresh2_i = thresh1_i / 2;
                candidate_peak_index_i = 0;
                candidate_peak_val_i[0] = thresh2_i;
                candidate_peak_val_i[1] = 0;

                spk_f = (candidate_peak_val_i[1] + 3*spk_f)/4;
                thresh1_f = npk_f + (spk_f - npk_f) / 2;
                thresh2_f = npk_f;
                candidate_peak_index_f = 0;
                candidate_peak_val_f[0] = 0;
                candidate_peak_val_f[1] = thresh2_f;
            }
            if (candidate_peak_index_f != 0 && candidate_peak_val_f[0] > thresh2_i) {
                beat_happened(candidate_peak_index_f,3);
                spk_i = (candidate_peak_val_f[0] + 3*spk_i)/4;
                thresh1_i = npk_i + (spk_i - npk_i) / 4;
                thresh2_i = thresh1_i / 2;
                candidate_peak_index_i = 0;
                candidate_peak_val_i[0] = thresh2_i;
                candidate_peak_val_i[1] = 0;

                spk_f = (candidate_peak_val_f[1] + 3*spk_f)/4;
                thresh1_f = npk_f + (spk_f - npk_f) / 2;
                thresh2_f = npk_f;
                candidate_peak_index_f = 0;
                candidate_peak_val_f[0] = 0;
                candidate_peak_val_f[1] = thresh2_f;
            }
        }
    }

    was_rising_i = int_is_rising_i;
    was_rising_f = int_is_rising_f;

    // roll over sample_count (to 2000) if it gets too big, make sure to correct last_R_sample and notify listener ??
    if (sample_count > 4294967285) {
        last_R_sample = 2000 - (sample_count - last_R_sample);
        reset_diff = sample_count - 2000;
        sample_count = 2000;
        did_reset = true;
    }

    // time out and reset if no beat detected in too long, notify listener
    if (sample_count > last_R_sample + 1000) {
        reset_diff = sample_count;
        sample_count = 0;
        last_R_sample = 0;
        beat_count = 0;
        average_RR2 = 1000;
        average_RR1 = 950;
        for (int i=0; i<8; i++){
            rr_intervals1[i] = 0;
            rr_intervals2[i] = 0;
        }
        for (int i=0; i<13; i++) {
            sample[i] = 0;
        }
        for (int i=0; i<33; i++) {
            low_pass[i] = 0;
        }
        for (int i=0; i<5; i++) {
            high_pass[i] = 0;
        }
        for (int i=0; i<30; i++) {
            squared[i] = 0;
        }
        integrated[0] = 0;
        integrated[1] = 0;
        thresh1_i = 9000;
        thresh2_i = 4500;
        spk_i = 9000;
        npk_i = 1500;
        thresh1_f = 1375;
        thresh2_f = 688;
        spk_f = 2500;
        npk_f = 1000;
        did_reset = true;
        prior_max_slope = 0;
    }
    sei();                                   // enable interrupts when youre done!
}// end isr


void beat_happened(long at_sample, int _peak_type){
    if (at_sample > last_R_sample + 40) {
        beat_count++;
        peak_type = _peak_type;
        if (beat_count > 1){
            update_RR_averages((at_sample - last_R_sample) * 5);
        }
        if (beat_count > 100) {
            beat_count = 10;
        }
        last_R_sample = at_sample;
        prior_max_slope = max_slope;
        max_slope = 0;
        QS = true;
    }
}

void update_RR_averages(int current_RR_interval){
    // sendDataToSerial('X', current_RR_interval);
    long sum = 0;
    int count = 0;
    for (int i=7; i > 0; i--) {
        rr_intervals1[i] = rr_intervals1[i-1];
        if (rr_intervals1[i] != 0){
            sum += rr_intervals1[i];
            count++;
        }
    }
    rr_intervals1[0] = current_RR_interval;
    sum += current_RR_interval;
    count++;
    average_RR1 = sum / count;

    sum = 0;
    count = 0;
    if (beat_count == 2) {
        average_RR2 = current_RR_interval;
        rr_intervals2[0] = current_RR_interval;
    } else {
        if (current_RR_interval * 100 > 92 * average_RR2 && current_RR_interval * 100 < 116 * average_RR2) {
            for (int i=7; i > 0; i--) {
                rr_intervals2[i] = rr_intervals2[i-1];
                if (rr_intervals2[i] != 0){
                    sum += rr_intervals2[i];
                    count++;
                }
            }
            rr_intervals2[0] = current_RR_interval;
            sum += current_RR_interval;
            count++;
            average_RR2 = sum / count;
            intervals_skipped = 0;
        } else {
            intervals_skipped++;
            if (intervals_skipped > 3) {
                average_RR2 = (average_RR2 + 3 * average_RR1) / 4;
                for (int i=0; i<8; i++) {
                    rr_intervals2[0] = 0;
                    intervals_skipped = 2;
                }
            }
        }
    }
}

void roll_array_l(volatile long array[], int N, volatile long new_value){
    // Newest data is stored on the lowest index of the array
    for (int i=N-1; i>0; i--){
        array[i] = array[i-1];
    }
    array[0] = new_value;
}

void roll_array_ul(volatile unsigned long array[], int N, volatile unsigned long new_value){
    // Newest data is stored on the lowest index of the array
    for (int i=N-1; i>0; i--){
        array[i] = array[i-1];
    }
    array[0] = new_value;
}

void serialOutput(){   // Decide How To Output Serial.
    if (did_reset && reset_diff != 0) {
        sendDataToSerial('R', reset_diff);
        did_reset = false;
        reset_diff = 0;
    }
    sendDataToSerial('S', sample_count);
    sendDataToSerial('K', sample[0]);
    sendDataToSerial('P', average_RR2);
    sendDataToSerial('O', average_RR1);

    int raw = analogRead(edr_pin);
    sendDataToSerial('G',  raw);
    if (average_RR2 == average_RR1 && beat_count > 7) {
        sendDataToSerial('N', 1);
    } else {
        sendDataToSerial('N', 0);
    }
    sendDataToSerial('F', high_pass[0]);
    sendDataToSerial('D', diff);
    sendDataToSerial('Q', squared[0]);
    sendDataToSerial('I', integrated[0]);
    sendDataToSerial('T', thresh1_i);
    sendDataToSerial('Y', thresh1_f);

}

//  Decides How To OutPut BPM and IBI Data
void beat_happened_notify(unsigned long sample_with_beat){
    sendDataToSerial('B',sample_with_beat);   // send the last beat time with a 'B' prefix
    sendDataToSerial('W',peak_type);

}

//  Sends Data to Pulse Sensor Processing App, Native Mac App, or Third-party Serial Readers.
void sendDataToSerial(char symbol, long data ){
    Serial.print(symbol);
    Serial.println(data);
    Serial.flush();
}

void test_blink(){
    digitalWrite(blinkPin, HIGH);
    delay(100);
    digitalWrite(blinkPin, LOW);
    delay(900);
}

void setup(){
    pinMode(blinkPin,OUTPUT);         // pin that will blink to your heartbeat!

    Serial.begin(115200);             // we agree to talk fast!
    // UN-COMMENT THE NEXT LINE IF YOU ARE POWERING The Pulse Sensor AT LOW VOLTAGE,
    // AND APPLY THAT VOLTAGE TO THE A-REF PIN
    //   analogReference(EXTERNAL);
    interruptSetup();                 // sets up to read Pulse Sensor signal every 2mS
}

//  Where the Magic Happens
void loop(){
    serialOutput();

    if (QS == true){     //  A Heartbeat Was Found
        digitalWrite(blinkPin,HIGH);     // Blink LED, we got a beat.
        beat_happened_notify(last_R_sample);
        QS = false;                      // reset the Quantified Self flag for next time
    } else {
        digitalWrite(blinkPin,LOW);            // There is not beat, turn off pin 13 LED
    }

    delay(33);  // take a break 20ms
}