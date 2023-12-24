December 24th, 2023:

Completed SigGen.py library.
Up to 6 signal generators can be instanciated, and will run using 0% CPU, 100% DMA.
Max tested output frequency: 4 MHz (fairly distorted).
Under 500 KHz output, very clean signal. Usage examples given at the end of dma.py and SigGen.py.
A low pass RC filter must be installed on output pins. Optionally also a decoupling capacitor to remove DC.
