%3E2EU370

; Idle prompt
030=   SHADYBUCKS

; Custom prompts
040=ENTER OTP #
041=LOGGED OUT
042=PRESS 8 TO LOGIN
043=LOGIN FAILED

; Primary phone number (suffix determines baud rate)
; M = 300 baud (Bell 103)
; N = 1200 baud (Bell 212A)
100=3033N
200=3033N
800=3033N

; Base32 encoded Shadybank token
214=

; [1] Sale
104=SALE
107$
  *L213 ; Ensure logged in and append Shadybank token
  Q     ; Write control character
  F1    ; "ENTER ACCOUNT #"
  E5.2  ; Numeric input, skip 5 commands if from cardreader
  C     ; Luhn check
  S     ; Begin dialing
  P40   ; "ENTER OTP #"
  K2.6  ; Numeric input from keypad, 6 digits
  I1    ; Skip 1 command
  C     ; Luhn check
  S     ; Begin dialing
  F3    ; "AMOUNT OF SALE"
  K4    ; Numeric input from keypad, 2 decimal places

; [2] Credit
204=CREDIT
207$
  *L213 ; Ensure logged in and append Shadybank token
  Q     ; Write control character
  F1    ; "ENTER ACCOUNT #"
  E5.2  ; Numeric input, skip 5 commands if from cardreader
  C     ; Luhn check
  S     ; Begin dialing
  P40   ; "ENTER OTP #"
  K2.6  ; Numeric input from keypad, 6 digits
  I1    ; Skip 1 command
  C     ; Luhn check
  S     ; Begin dialing
  F11   ; "AMOUNT OF CREDIT"
  K4    ; Numeric input from keypad, 2 decimal places

; [3] Balance
; TODO: Implement.

; [8] Log In
804=LOGIN
807$
  R    ; Append field separator (no Shadybank token)
  Q    ; Write control character
  F1   ; "ENTER ACCOUNT #"
  E.2  ; Numeric input from cardreader or keypad
  C    ; Luhn check
  P40  ; "ENTER OTP #"
  K2.6 ; Numeric input from keypad, 6 digits
810$
  B2.3
  +S2.0.#0 ; Get length of buffer
  +A#0.0.3.4 ; Skip 4 commands if response is 3 character (STX, ETX, LRC)
  O
  X.3
  U214.3  ; Copy response to Shadybank token memory location
  *K0     ; Abort and display the idle prompt
  B3.3    ; Buffer 3 source and dest
  G       ; Clear buffer
  A43     ; "LOGIN FAILED"
  V.2     ; Display buffer
  *K1     ; Abort and leave existing diplay

; [9] Log Out
; TODO: Actually invalidate token.
904=LOGOUT
907$
  B3.3  ; Buffer 3 source and dest
  G     ; Clear buffer
  U214  ; Copy empty buffer to Shadybank token memory location
  A41   ; "LOGGED OUT"
  V.2.2 ; Display buffer, wait 1 second
  *K0   ; Abort and display the idle prompt

; Ensure logged in and append Shadybank token
213$
  A214.2 ; Read Shadybank token memory location, skip 2 commands if empty
  R      ; Append field seperator
  *M     ; Return
  B3.3   ; Buffer 3 source and dest
  G      ; Clear buffer
  A41    ; "LOGGED OUT"
  V.2.2  ; Display buffer, wait 1 second
  A42    ; "PRESS 8 TO LOGIN"
  V.2.2  ; Display buffer, wait 1 second
  *K0    ; Abort and display the idle prompt

; Disable other buttons
304=1
307=*K0  ; Abort and display the idle prompt
404=1
407=*K0  ; Abort and display the idle prompt
504=1
507=*K0  ; Abort and display the idle prompt
604=1
607=*K0  ; Abort and display the idle prompt
704=1
707=*K0  ; Abort and display the idle prompt
