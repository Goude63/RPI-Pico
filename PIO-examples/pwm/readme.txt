Pulse width modulation PIO example 1-4 channels
The class has a waveform method to generate sine/triangle and sawtooth waves

Current version cannot play waveforms simultanousely on multiple channels
because the sm.put() method is blocking. It can however set specific DC values
on all 4 channels.

The examples creates just one channel and plays a sine then a sawtooth, 
then a triangle waveform.

Part of the PIO code is inpired by Toby Roberts example, with minor improvments
