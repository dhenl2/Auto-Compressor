# Auto-Compressor
**As a** person pumping up tyres  
**I would like** to select a target pressure for each of tyres to be inflated/deflated to  
**so that** it is more convenient than if I was to do it manually.

Goal is to create a system that can:
- Control air flow going in and out of the tyre
	- Will need time to target estimation for minimal inflation/deflation disruptions and increased accuracy
		- Just for fun :grin: 
	- Usage on an embedded device using MicroPython
- Create an UI for mobile devices
	- Either web or mobile application interface
	- Communicate via either Bluetooth or WIFI
- Make it cost effective
- Create instruction set suitable for the DIY public to modify their existing pump

## Design V2 - Integrated Module
Plan is to modify the existing trigger for the pump to make it controllable via the relay module. This will remove a solenoid valve but the remaining componentry will be the same. It's less accessible but will be cheaper.

#### Table of Costs
| Description | Units | Cost / Item | Total|
|------|-----|-----|-----|
| Solenoid Valve N.C | 1 | $77 | $77|
| 1/4" to Barb | 2 | $12.95 2pk | $12.95 |
| 1/4" to Coupling | 1 | $17.95 2pk | $8.98 |
| T Barb Joiner | 2 | $13.95 | $25.90 |
| Hose Clamps | 8 | $6.95 4pk | $13.90 |
| Air Presure Sensor | 1 | $20.23 | $20.23 |
| 2 Channel Relay | 1 | $6.96 | $6.96 |
| ESP8266 | 1 | $3.88 | $3.88 |
| | | **Total** | **$169.80**|

#### Diagram
![Slim Design](diagrams/diagramSlim.png)

## Design V1 - Independent Module
Plan to was to create an entirely separate module from the compressor to be publicly sold. It was discovered that the sum of the products would not be competitive with the [current opposition](https://www.4wdevo.com.au/product/autoflate/) ($375 if available...). 2 solenoid valves would be equal to $180 without considering other components. So it will be scrapped.

#### Table of Costs
| Description | Units | Cost / Item | Total|
|------|-----|-----|-----|
| Solenoid Valve N.O | 1 | $104.50 | $104.50|
| Solenoid Valve N.C | 1 | $77 | $77|
| 1/4" to Barb | 2 | $12.95 2pk | $12.95 |
| 1/4" to Coupling | 2 | $17.95 2pk | $17.95 |
| T Barb Joiner | 2 | $13.95 | $25.90 |
| Hose Clamps | 8 | $6.95 4pk | $13.90 |
| Air Presure Sensor | 1 | $20.23 | $20.23 |
| 2 Channel Relay | 1 | $6.96 | $6.96 |
| ESP8266 | 1 | $3.88 | $3.88 |
| | | **Total** | **$283.27**|

#### Diagram

![diagram](diagrams/diagram.png)

