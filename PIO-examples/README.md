# pico-PIO-examples
Practical examples for raspberry pi pico PIO coding in micropython

I am fairly new to python so be forgiving.
I make these examples mostly to show how to use the raspberry pi pico PIO instructions
The examples I saw elsewhere are often limited to blinking a led

The first example is a 4 channel uart that uses 5 instructions for rx and 6 for tx!
The second example is a PWM class that can generate and "play" waveforms (sine, sawtooth...)
Note that this is academic only: actual pico PWM slices should be used to generate PWM signals!

Examples 3-4: pio_ewlnk.py and pio_x10rf.py show how to decode x10 rf messages and EV1527 rf messages.
Both examples need the correct demodulator circuit that outputs 1 when rf present and zero otherwise.
The png images show the messages format and bit encoding
