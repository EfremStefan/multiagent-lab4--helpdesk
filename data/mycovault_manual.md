# MycoVault MV-200 User & Service Manual

This document is fictional and was written for the MAS lab.

## 1. Product Overview

The MycoVault MV-200 is a 120-litre climate-controlled cabinet for indoor cultivation of gourmet mushrooms. It has four removable perforated shelves, an ultrasonic humidifier fed from a 4-litre water reservoir, a Peltier heating/cooling module, a CO2 sensor (NDIR), a fresh-air exchange (FAE) fan with HEPA H13 filter, full-spectrum LED lighting and the SporeEye camera that detects green and black mould. Firmware version at the time of writing: 3.4.2.

## 2. Technical Specifications

- Temperature range: 12–30 °C (accuracy ±0.5 °C).
- Humidity range: 60–98 % RH.
- CO2 measurement: 400–5000 ppm.
- Power supply: 220–240 V AC, 50 Hz; average consumption 45 W, peak 140 W.
- Ambient operating conditions: 15–28 °C room temperature. Do not install in direct sunlight.
- Weight (empty): 23 kg. Minimum clearance: 10 cm at the back for the FAE fan.

## 3. Installation

Place the unit on a level surface. Fill the reservoir with distilled or demineralised water only; tap water causes white mineral dust on mushrooms and blocks the humidifier membrane. On first start-up the unit performs a 20-minute self-calibration; do not open the door during this time. Connect to the MycoVault app via the 2.4 GHz Wi-Fi network only (5 GHz is not supported).

## 4. Control Panel

The panel has four buttons: MODE, FAN, LIGHT and OK. Press MODE to cycle through the stages Colonisation → Pinning → Fruiting. Hold OK for 3 s to lock the panel (child lock); hold OK again for 3 s to unlock. A factory reset is done by holding MODE + OK for 10 s; it erases custom profiles but not Wi-Fi settings.

## 5. Cultivation Profiles (Fruiting stage)

| Species | Temp. (°C) | Humidity (%) | CO2 max (ppm) | Light (h/day) |
|---|---|---|---|---|
| Blue Oyster | 18–22 | 90 | 800 | 12 |
| Pink Oyster | 24–28 | 88 | 900 | 12 |
| Shiitake | 16–20 | 85 | 1000 | 10 |
| Lion's Mane | 18–21 | 94 | 700 | 8 |
| King Trumpet | 14–17 | 87 | 1500 | 10 |

During Colonisation the light is off, the FAE fan runs only 2 minutes per hour and CO2 may rise up to 5000 ppm; this is normal. Lion's Mane develops long, stringy "teeth" and coral shapes if CO2 exceeds 700 ppm – increase FAE using the FAN button (level 3 or higher).

## 6. Maintenance

- Replace the HEPA H13 filter every 90 days (part no. MV-F13).
- Descale the humidifier every 30 days with a 5 % citric acid solution: fill the reservoir, run the program CLEAN (MODE + FAN, 3 s) for 15 minutes, then rinse twice with distilled water.
- Clean the chamber with 70 % isopropyl alcohol or 3 % hydrogen peroxide.
- Never use chlorine bleach: chlorine vapour permanently damages the NDIR CO2 sensor and voids the warranty.
- Wipe the SporeEye camera lens with a dry microfibre cloth only.

## 7. Error Codes

| Code | Meaning | Action |
|---|---|---|
| E01 | Water reservoir low | Refill with distilled water. Humidifier stops automatically. |
| E03 | Door open > 5 min | Close the door. Alarm stops automatically. |
| E07 | CO2 sensor drift | Move the unit to fresh air (or open a window), empty the chamber, then hold FAN + LIGHT for 5 s. Recalibration takes 8 minutes. |
| E09 | Humidifier membrane blocked | Run the CLEAN program (Section 6). If E09 persists after cleaning, replace membrane MV-M2. |
| E12 | Contamination detected by SporeEye | The unit enters Quarantine Mode (FAE stops, door lock on). Wear an FFP2 mask, remove and seal the affected block in a bag, disinfect the chamber, then press OK to exit Quarantine. |
| E15 | Wi-Fi connection lost | Check that the router broadcasts 2.4 GHz. Device keeps working offline. |
| E19 | Peltier module overheat | Unit pauses heating/cooling for 30 minutes. Check 10 cm rear clearance and room temperature. |
| E23 | Firmware integrity error | Do not power off. Device restores firmware 3.4.2 from backup within 10 minutes. |

## 8. Safety

Mature mushrooms release large amounts of spores which can cause allergic reactions ("mushroom worker's lung"). Wear an FFP2 mask when harvesting Oyster species and when handling contaminated blocks. Children under 12 must not operate the unit unsupervised. Unplug the unit before any maintenance except the CLEAN program.

## 9. Warranty and Service

The MV-200 has a 24-month warranty from the date of purchase. The warranty is void if: unofficial firmware is installed, chlorine bleach was used, or the unit was opened by a non-authorised person.

A service technician must be contacted (ticket required) when:

1. E19 occurs twice within 24 hours;
2. E23 does not clear within 10 minutes (high priority);
3. E07 reappears within 7 days after recalibration;
4. there is any smell of burning, smoke or water leaking under the unit (high priority; customer must unplug immediately).

Customer support hours: Monday–Friday 09:00–17:00 CET.
