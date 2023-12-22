This example creates 1-4 uarts using PIO coding.
as per PIO capability, the same tx code is used for all channels.
Same for rx code. 

The file pio_uarts.py can be save in the /lib folder of the pico for import
The file test_uarts.py shows how to use the library. It will create 4 uarts
and send random numbers (as ascii strings) and verify that, through a loopback
jumper, each channel receives the same random strings that are sent.

I have a fair amout of experience with micro-comtrollers, but I'm faily new 
to python, so be nice/constructive! 

I may add additionnal memory FIFOs in the future because the PIO fifos are limited
to 8 entries. I would create ram FIFOS and would use the second pico core to handle
tx and rx buffering
