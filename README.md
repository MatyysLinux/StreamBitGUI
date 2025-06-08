# StreamBit  
A DIY StreamDeck made from MicroBit/s.

## Installation  
First, you will need a [MicroBit v2](https://www.amazon.com/Micro-Original-Starter-Microbit-Battery/dp/B0F1DQTT79).
You can have two of [them](https://www.amazon.com/Micro-Original-Starter-Microbit-Battery/dp/B0F1DQTT79) if you want.
Next, ensure [Python](https://www.python.org/downloads) 3 is installed on your Windows PC.  
Open CMD or Terminal and run:  
```
pip install pyserial
```
Flash "microbit1.hex" onto the first MicroBit (then flash "microbit2.hex" onto the second MicroBit).  
On your PC, double-click "streambitgui.pyw" and configure your COM ports (you can find these in Device Manager under Ports when the MicroBits are connected), as well as commands you want to start.

## Usage  
Run "streambitgui.pyw" and wait for the program to load the config file (config.json) then press Start Server. Now just wait for the PC and MicroBit/s to establish a connection.  
Pressing buttons A, B or A+B on the MicroBit/s will launch the assigned commands or open specified directories, you can also shake the MicroBit or touch one of the pins on the board (place your finger on GND then touch pin 0, 1 or 2).  
