# CHAPTER 3: FAULT DIAGNOSIS AND TROUBLESHOOTING

## 3.0 GENERAL OVERVIEW
The Radio set features a modular physical design. This allows faults to be easily traced and pin-pointed by isolating the faulty module whenever the set fails to operate. Repairing a faulty set effectively requires a solid background knowledge of the system's operational architecture. 

When the Receiver Transmitter develops a fault, follow the troubleshooting procedures outlined below. Many symptoms are discussed alongside their probable faulty modules or components. If a module is suspected, validate its performance before replacing it with a spare module to prevent the arbitrary replacement of functional hardware. For deeper hardware servicing, reference *Technical Mechanical Part III: Overhaul and Reconditioning Instructions*.

> ### ⚠️ CRITICAL SAFETY CAUTION
> **ENSURE THE RADIO SET IS COMPLETELY SWITCHED OFF WHILE REPLACING MODULES OR CONNECTORS DURING TROUBLESHOOTING OF THE RADIO UNDER TEST.**

---

## 3.1 SYSTEMATIC TROUBLESHOOTING MATRIX
The troubleshooting procedures are covered systematically by system layer and then card/module wise. Use the following sequential layout for fault diagnosis:
* **Procedure 1:** Dead Unit Troubleshooting Flowchart (Followed when the Radio Set is dead)
* **Procedure 2:** BITE Check Matrix (Used to check the failure of any module via internal diagnostics)
* **Procedure 3:** Display / Keypad Subsystem Troubleshooting (Locates faults related to display errors or keypad input)
* **Procedure 4:** Receiver Path (Rx) Troubleshooting (Followed whenever there is no reception in the Radio Set)
* **Procedure 5:** Transmitter Path (Tx) Troubleshooting (Followed whenever there is a transmission problem with the radio set)

---

### PROCEDURE 1: Dead Unit Troubleshooting Flowchart
*Follow this procedure if the handheld terminal fails to turn ON.*

1. **Battery Voltage Check:**
   * **Action:** Check the battery voltage to ensure it is properly charged.
   * **If Voltage is Low:** Charge the Battery.
   * **If Voltage is Sufficient (Yes):** Proceed to step 2.
2. **Main Power Interface Test:**
   * **Action:** Check the voltage baseline directly at test point **TP 34**.
   * **Target Metric:** It should measure `~7.4V` or match the nominal battery voltage.
   * **If Voltage is Absent/Incorrect:** * **Root Cause:** Battery connection issue.
   * **If Voltage is Correct (Yes):** Proceed to step 3.
3. **Core Regulator Rails Test:**
   * **Action:** Check the voltage lines at **TP 35** and **TP 36**.
   * **Target Metrics:** **TP 35** must measure `3.6V`; **TP 36** must measure `5V`.
   * **If Rails are Absent/Incorrect:**
     * **Root Cause:** **U24** Power component is Faulty.
   * **If Rails are Correct (Yes):** Proceed to step 4.
4. **Logic Supply Check:**
   * **Action:** Check the voltage baseline at resistor component **R55**.
   * **Target Metric:** It should measure `3.3V`.
   * **If 3.3V Line is Absent (No):** Proceed to evaluate downstream components.
   * **If 3.3V Line is Present (Yes):**
     * **Root Cause:** **U29** component is Faulty.
5. **Execution Verification:**
   * **Condition (Yes):** If the core power steps are valid but the screen remains unresponsive:
     * **Root Cause:** Display is Faulty.
     * **Action:** Check and validate the display assembly using a specialized test jig
    

### PROCEDURE 2: BITE Check Matrix

*Follow this procedure to check for the failure of any module via internal diagnostics.* 

1. **Initial Setup & Initialization:**
* **Action:** Connect the battery to the Radio Set and connect the Antenna to the Radio. 

*  **Action:** Switch on the Radio Set and then navigate to the menu list and select **iBITE**. 

* **Next Step:** Proceed to step 2.

2. **Baseband Layer Test:**
* **Condition:** Does the Display show **`BB:OK`**? 

* **If No:** * **Root Cause / Action:** In the Baseband card, reprogram the SCT. 

* **If Yes:** Proceed to step 3.

3. 
* **Condition:**  Does the Display show **`RF:OK`**? 

* **If No:** * **Root Cause / Action:** Check the RF path and reprogram the SCT. 
  **Root Cause:** The RTC (Real-Time Clock) may be Faulty or the SPI flash may be faulty in the SM Card. 

* **If Yes:** Proceed to step 4.


4. 
* **Condition:**  Does the Display show **`F:1`**? 

* **If Yes:** * **Root Cause:** The FPGA may be faulty in the SM card. 
* **If No:** Proceed to step 5.


5. 
* **Condition:** Does the Display show **`S:1`**? 
* **If Yes:** * **Root Cause:** SPI flash may be faulty in SM card.

* **If No:** Proceed to step 6.

6. 
* **Condition:**  Does the Display show **`R:1`**? 

* **If Yes:** RTC may be faulty in SM card.
* **If No:** The built-in diagnostics check has passed with no active module faults detected.



### PROCEDURE 3: Display / Keypad Subsystem Troubleshooting

Follow this procedure to locate the fault whenever there is any problem with the display or keypad.

1. **Initial Power Setup:**
* **Action:** Connect the Battery to the Radio Set, connect the Antenna to the Radio, and Switch ON the Radio.


* **Next Step:** Proceed to step 2.


2. **Visual Character Verification:**
* **Condition:** Does the Display show proper characters?


* **If Yes:** Proceed to step 4 (Keypad Input Diagnostics).


* **If No:** Proceed to step 3.




3. **Display Rendering Diagnostics:**
* **Condition:** Is the Display Missing or Unwanted Character Displayed?


* 
**If Yes:** * **Root Cause / Action:** Check proper connection of display cable, or the Display is Faulty.
* 
**If No:** Display is confirmed functional (Display Ok).





4. **Keypad Input Diagnostics:**
* 
**Action:** Select compose (**Menu** ➔ **Message** ➔ **Compose**) and check all keys.

**Condition:** Is Digit Display Proper?
* 
**If No:** * **Root Cause:** Keypad or Keypad Cable is faulty.


* 
**If Yes:** * **Execution Verification:** Keypad & Display are confirmed fully functional (Keypad & Display OK).



### PROCEDURE 4: Troubleshooting in Receiver Path

*Follow this procedure whenever there is no reception in the Radio Set.*

1. **Symptom Identification:**
* **Observed Issue:** Bad SINAD / No recovered audio.
* **Action:** Proceed directly to Step 2.


2. **RSSI Display Test:**
* **Condition:** Is the RSSI sign displayed when RF is turned on?
* **If YES:** *Proceed to Audio Subsystem Path:*
* **Action:** Check audio at **C21**.
* **Condition:** Is audio present at C21 (Yes)?
* **Action:** Check **Speaker**.




* **If NO:** *Proceed to Local Oscillator Path (Step 3).*


3. **Local Oscillator (L.O.) Verification:**
* **Action:** Check L.O Freq At **C114**. (Target Metric: Double the channel freq).
* **If YES (Correct Freq):** Proceed to Regulator Rails Test (Step 5).
* **If NO (Incorrect Freq):** Proceed to Master Clock Check (Step 4).


4. **Master Clock Check:**
* **Action:** Check freq `38.4 MHz` at **U38**.
* **If YES (Correct Freq):** *No downstream path specified, evaluate local trace.*
* **If NO (Incorrect Freq):** * **Root Cause:** **TCXO** Faulty.


5. **Regulator Rails Test:**
* **Action:** Check voltage at **L37**. (Target Metric: `1.2V`).
* **If YES (Correct Voltage):**
* **Root Cause:** **U4** Faulty.


* **If NO (Incorrect Voltage):**
* **Root Cause:** **U21** Faulty.



### PROCEDURE 5: Troubleshooting in Transmitter

*Follow this procedure whenever there is a transmission problem with the radio set.*

1. **Initial Fault Symptom Validation:**
* **Observed Issue:** TX not working.
* **Action:** Press PTT switch and observe the status LED.
* **Branching Condition:** Does the RED LED glow when PTT is pressed?
* **If RED LED DOES NOT glow:** Proceed to **Branch A (LED Fault Logic)**.
* **If RED LED GLOWS (PTT ON path):** Proceed to **Branch B (RF Power Logic)**.





---

#### BRANCH A: LED Fault Logic (RED LED Doesn't Glow)

2. **PTT Switch Mechanical Check:**
* **Action:** Check shorting of **SW 5** when pressed.
* **If NO:** * **Root Cause:** **SW 5** Faulty.
* **If YES:** Proceed to step 3.


3. **Controller Line Toggling Check:**
* **Action:** Check toggling at **R248** on PTT pressing.
* **If NO:** * **Root Cause:** Controller Faulty.
* **If YES:** Proceed to step 4.


4. **Regulator Rail Check:**
* **Action:** Check voltage at **L37**. *(Target Metric: `1.2V`)*
* **If NO:** * **Root Cause:** **U21** Faulty.
* **If YES:** * **Root Cause:** **U4** Faulty.



---

#### BRANCH B: RF Power Logic (PTT ON / RED LED Glows)

5. **Reference Clock Distribution Check:**
* **Action:** Check `38.4 MHz` signal at inductor **L42**.
* **If NO:** * **Root Cause:** **U38** Faulty.
* **If YES:** Proceed to step 6.


6. **Transmitter Line Toggling Check:**
* **Action:** Check toggling at **R179** on PTT pressing.
* **If NO:** * **Root Cause:** **U4** Faulty.
* **If YES:** *All specified component diagnostic checks passed; evaluate secondary downstream matching network blocks.*