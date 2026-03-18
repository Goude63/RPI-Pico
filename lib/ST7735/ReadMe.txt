This ST7735 driver is taken from various sources that are related: boochow, GuyCarver.

I modified the code so that it can work with font data that has more than 8 pixel height,
and for font data that has its bit endienness reversed.

I also added code to drive the led with PWM allowing ajustment of display brightness

I removed the support to multiply character size by an integer because it now looks MUCH better 
using bigger fonts instead.

I am using this library for a 4 channel signal generetor project using a DAC8822 and if display response is
 too slow, I may also go over some functions and try incorporating viper code :)
