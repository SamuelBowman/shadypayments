#!/usr/bin/env python3
import argparse
import re
import requests
import serial
import time
import traceback
from base64 import b32encode, b32decode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modem-port', required=True)
    parser.add_argument('--shadybank-backend', required=True)
    args = parser.parse_args()

    modem = Modem(args.modem_port)
    shadybank = Shadybank(args.shadybank_backend)

    while True:
        modem.wait_for_carrier()
        print('Connected')

        try:
            request = modem.recv_request()
            response = process_request(shadybank, request)
            modem.send_response(response)
        except Exception as e:
            print(traceback.format_exc())

        print('Hang up')
        modem.hang_up()

class Modem():
    def __init__(self, modem_port):
        self.modem = serial.Serial(
            port=modem_port,
            baudrate=9600,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=True,
            dsrdtr=True,
            timeout=30,
        )
        modem_init_string = b'ATE0Q1&D2&C1S0=1L2M2&Q6\r\n'
        print(f'Send modem init string: {modem_init_string}')
        self.modem.write(modem_init_string)

    def wait_for_carrier(self):
        while not self.modem.cd:
            time.sleep(1)

    @staticmethod
    def calculate_lrc(data):
        assert len(data) >= 1
        lrc = 0
        for byte in data[1:]:
            lrc ^= byte
        return lrc.to_bytes()
    
    @staticmethod
    def verify_lrc(data, lrc):
        if len(data) < 2 or data[0] != 2 or data[-1] != 3:
            return False
        return lrc == Modem.calculate_lrc(data)

    def recv_request(self):
        received_data = False
        for i in range(3):
            if not received_data:
                print('Send ENQ')
                self.modem.write(b'\x05')
            data = self.modem.read_until(b'\x03')  # ETX
            print(f'Data: {data}')
            if data:
                received_data = True
            else:
                print('No data')
                continue
            lrc = self.modem.read()
            print(f'LRC: {lrc}')
            if Modem.verify_lrc(data, lrc):
                print('Valid LRC, send ACK')
                self.modem.write(b'\x06')
                return data
            else:
                print('Invalid LRC, send NAK')
                self.modem.write(b'\x15')
        raise Exception('Failed to receive request')
    
    def send_response(self, response):
        for i in range(3):
            print(f'Send response: {response}')
            self.modem.write(response)
            self.modem.write(Modem.calculate_lrc(response))
    
            maybe_ack = self.modem.read()
            if maybe_ack == b'\x06':  # ACK
                print('Send EOT')
                self.modem.write(b'\x04')  # EOT
                return

    def hang_up(self):
        self.modem.dtr = False
        time.sleep(2)
        self.modem.dtr = True

class Shadybank():
    def __init__(self, backend):
        assert not backend.endswith('/')
        self.backend = backend
        self.token = None

    def with_token(self, token):
        new_shadybank = Shadybank(self.backend)
        new_shadybank.token = token
        return new_shadybank

    def post(self, api, data):
        if self.token:
            return requests.post(f'{self.backend}/api/{api}', headers={'Authorization': f'Bearer {self.token}'}, data=data)
        else:
            return requests.post(f'{self.backend}/api/{api}', data=data)

    def login(self, **data):
        response = self.post('login', data)
        if response.status_code == 201:
            shadybank_token = response.text
            shadybank_token = shadybank_token.encode('ascii')
            shadybank_token = b32encode(shadybank_token)
            print(f'Login succeeded {shadybank_token}')
            return b'\x02' + shadybank_token + b'\x03' 
        else:
            print('Login failed')
            return b'\x02\x03'
    
    def authorize_and_capture(self, **data):
        response = self.post('authorize', data)
        if response.status_code == 200:
            auth_code = response.text
            print(f'Auth Code: {auth_code}')
            return self.capture(auth_code=auth_code, amount=data['amount'])
        elif response.status_code == 404 and 'Voice auth required' in response.text:
            print('Voice auth required')
            # TODO: Make TCL program dial BUXX if phone connected.
            return b'\x02NEED VOICE AUTH\x03'
        else:
            print('Authorization failed')
            return b'\x02AUTH FAILED\x03'
    
    def capture(self, **data):
        response = self.post('capture', data)
        if response.status_code == 204:
            print('Capture succeeded')
            return b'\x02PAYMENT SUCCEED\x03'
        else:
            print('Capture failed')
            return b'\x02CAPTURE FAILED\x03'

    def credit(self, **data):
        response = self.post('credit', data)
        if response.status_code == 204:
            print('Credit succeeded')
            return b'\x02CREDIT SUCCEEDED\x03'
        else:
            print('Credit failed')
            return b'\x02CREDIT FAILED\x03'

track_1_regex = re.compile(r'(?a)\x02(?P<cmd>[^\x1c]+)\x1c(?P<token>[^\x1c]*)\x1c(?P<wcc>[AC])B(?P<pan>\d{8,19})\x1f(?P<name>.*)\x1f(?P<exp>\d{4})(?P<svc>\d{3})(?P<dd1>[^\x1c]+)(?:\x1c(?P<otp>\d{6}))?(?:\x1c(?P<amount>\d+\.\d\d))?\x03')
track_2_regex = re.compile(r'(?a)\x02(?P<cmd>[^\x1c]+)\x1c(?P<token>[^\x1c]*)\x1c(?P<wcc>[AC])(?P<pan>\d{8,19})=(?P<exp>\d{4})(?P<svc>\d{3})(?P<dd2>[^\x1c]+)(?:\x1c(?P<otp>\d{6}))?(?:\x1c(?P<amount>\d+\.\d\d))?\x03')
keypad_regex = re.compile(r'(?a)\x02(?P<cmd>[^\x1c]+)\x1c(?P<token>[^\x1c]*)\x1c(?P<wcc>[@B])(?P<pan>\d{8,19})\x1c(?P<otp>\d{6})(?:\x1c(?P<amount>\d+\.\d\d))?\x03')

def process_request(shadybank, data):
    data = data.decode('ascii')

    track_1_match = track_1_regex.fullmatch(data)
    if track_1_match:
        print(f"Track 1")
        print(f"Command: {track_1_match['cmd']}")
        shadybank_token = b32decode(track_1_match['token']).decode('ascii')
        print(f"Shadybank Token: {shadybank_token}")
        print(f"Write Control Character: {track_1_match['wcc']}")
        print(f"Primary Account Number: {track_1_match['pan']}")
        print(f"Name: {track_1_match['name']}")
        print(f"Expiration Date: {track_1_match['exp']}")
        print(f"Service Code: {track_1_match['svc']}")
        print(f"Discretionary Data 1: {track_1_match['dd1']}")
        print(f"OTP: {track_1_match['otp']}")
        print(f"Amount: {track_1_match['amount']}")
        track_1_for_shadybank = f"%B{track_1_match['pan']}^{track_1_match['name']}^{track_1_match['exp']}{track_1_match['svc']}{track_1_match['dd1']}?"
        match track_1_match['cmd']:
            case 'SALE':
                return shadybank.with_token(shadybank_token).authorize_and_capture(track1=track_1_for_shadybank, amount=track_1_match['amount'])
            case 'CREDIT':
                return shadybank.with_token(shadybank_token).credit(pan=track_1_match['pan'], amount=track_1_match['amount'])
            case 'LOGIN':
                return shadybank.login(pan=track_1_match['pan'], otp=track_1_match['otp'])

    track_2_match = track_2_regex.fullmatch(data)
    if track_2_match:
        print(f"Track 2")
        print(f"Command: {track_2_match['cmd']}")
        shadybank_token = b32decode(track_2_match['token']).decode('ascii')
        print(f"Shadybank Token: {shadybank_token}")
        print(f"Write Control Character: {track_2_match['wcc']}")
        print(f"Primary Account Number: {track_2_match['pan']}")
        print(f"Expiration Date: {track_2_match['exp']}")
        print(f"Service Code: {track_2_match['svc']}")
        print(f"Discretionary Data 2: {track_2_match['dd2']}")
        print(f"OTP: {track_2_match['otp']}")
        print(f"Amount: {track_2_match['amount']}")

        track_2_for_shadybank = f";{track_2_match['pan']}={track_2_match['exp']}{track_2_match['svc']}{track_2_match['dd2']}?"
        match track_2_match['cmd']:
            case 'SALE':
                return shadybank.with_token(shadybank_token).authorize_and_capture(track2=track_2_for_shadybank, amount=track_2_match['amount'])
            case 'CREDIT':
                return shadybank.with_token(shadybank_token).credit(pan=track_2_match['pan'], amount=track_2_match['amount'])
            case 'LOGIN':
                return shadybank.login(pan=track_2_match['pan'], otp=track_2_match['otp'])

    keypad_match = keypad_regex.fullmatch(data)
    if keypad_match:
        print(f"Keypad")
        print(f"Command: {keypad_match['cmd']}")
        shadybank_token = b32decode(keypad_match['token']).decode('ascii')
        print(f"Shadybank Token: {shadybank_token}")
        print(f"Write Control Character: {keypad_match['wcc']}")
        print(f"Primary Account Number: {keypad_match['pan']}")
        print(f"OTP: {keypad_match['otp']}")
        print(f"Amount: {keypad_match['amount']}")

        match keypad_match['cmd']:
            case 'SALE':
                return shadybank.with_token(shadybank_token).authorize_and_capture(pan=keypad_match['pan'], otp=keypad_match['otp'], amount=keypad_match['amount'])
            case 'CREDIT':
                return shadybank.with_token(shadybank_token).credit(pan=keypad_match['pan'], amount=keypad_match['amount'])
            case 'LOGIN':
                return shadybank.login(pan=keypad_match['pan'], otp=keypad_match['otp'])

    raise Exception('Failed to parse request')

if __name__ == '__main__':
    main()
