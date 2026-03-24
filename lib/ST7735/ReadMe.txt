This ST7735 driver is taken from various sources that are related: boochow, GuyCarver.

Changes:
1- I modified the code so that it can work with font data that has more than 8 pixel height,
   and for font data that has its bit endienness reversed. It is fairly easy to modify some
   c and h files that can be found here and there. See the 'fonts' folder for examples

2- Change text/char function to work with any background color instead of just black

3- Added code to drive the led with PWM allowing ajustment of display brightness

4- I removed the support to multiply character size by an integer because it now looks MUCH better 
   using bigger fonts instead.

5- Some font files have pixel matrix reversed x vs y. This driver only support fonts files where hexadecimal 
   values correspond to vertical columns of bits. If you try to convert files that have it the other way around, 
   characters wil show sideways by 90 degrees. It would not be that hard to write a converter function...

I am using this library for a 4 channel signal generetor project using a RP2 and a DAC8822. If display response is
 too slow, I may also go over some functions and try incorporating viper code :)
