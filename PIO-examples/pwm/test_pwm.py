from pio_pwm import PWM 

# PWM signals are sent on GP16/physical pin 21
# it needs to be filtered to show as analog output
#
#            220 ohms   22 nF      1 uF
#   pin 21 ---/\/\-------||----+----||----> (probe/speaker +)
#                              |
#                              |
#                              V
#                             GND (pin 23)
#                       (probe/speaker -)

tst = PWM()
tst.send(0, 50) # 50% duty cycle

#generate example wave arrays
sin = tst.wav(0,"sin", wf=5000)  #  5 kHz sine
saw = tst.wav(0,"saw", wf=10000) # 10 kHz saw tooth
tri = tst.wav(0,"tri", wf=8000)  #  8 kHz triangle

#play 2 second each  : (2 * wf) cycles
tst.send(0,sin,10000)
tst.send(0,saw,20000)
tst.send(0,tri,16000)

tst.send(0,50)