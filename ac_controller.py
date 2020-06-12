# ECHONET Lite
# https://echonet.jp/spec_g/

import enum
import json
import socket
import sys
import typing
import urllib.request

class Service(enum.Enum):
    SET_I = 0x60
    SET_C = 0x61
    GET = 0x62
    INF_REQ = 0x63
    SET_GET = 0x6e

class Property(enum.Enum):
    STATUS = 0x80
    MODE = 0xb0
    TEMPERATURE = 0xb3

class Status(enum.Enum):
    ON = b'\x30'
    OFF = b'\x31'

class Mode(enum.Enum):
    AUTOMATIC = b'\x41'
    COOLING = b'\x42'
    HEATING = b'\x43'
    DEHUMIDIFICATION = b'\x44'
    AIR_CIRCULATOR = b'\x45'
    OTHER = b'\x40'

MULTICAST_ADDRESS = '224.0.23.0'
PORT = 3610

SOCKET_BUFSIZ = 4096

def number(v: str):
    """Try to convert the given value to int, then float.
    If the conversion is failed, return the value as-is.
    """
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v

def create_frame(service: Service, properties: typing.Dict[Property, bytes]) -> bytearray:
    f = bytearray.fromhex(
        '1081' # EHD
        + '0000' # TID
        + '05ff01' # SEOJ (Controller)
        + '013001') # DEOJ (Home air conditioner)
    f.append(service.value) # ESV
    f.append(len(properties)) # OPC
    for k, v in properties.items():
        f.append(k.value) # EPC
        f.append(len(v)) # PDC
        f.extend(v) # EDT
    return f

def find_air_conditioner() -> str:
    """Returns an IP address of a home air conditioner."""
    # System Design Guidelines, Section 4.3
    f = create_frame(Service.GET, {Property.STATUS: b''})
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('0.0.0.0', PORT))
        s.sendto(f, (MULTICAST_ADDRESS, PORT))
        _, address = s.recvfrom(SOCKET_BUFSIZ)
    return address[0]

def get_sensor_info(host: str) -> dict:
    """Returns a dict like:
    {'ret': 'OK', 'htemp': 20.0, 'hhum': 25, 'otemp': 6.0, 'err': 0, 'cmpfreq': 0, 'mompow': 1}
    """
    info = dict()
    with urllib.request.urlopen('http://' + host + '/aircon/get_sensor_info') as f:
        for e in f.read().decode('utf-8').split(','):
            kv = e.split('=', 1)
            info[kv[0]] = number(kv[1])
    return info

def turn_off(host: str) -> None:
    f = create_frame(Service.SET_I, {Property.STATUS: Status.OFF.value})
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(f, (host, PORT))

def turn_on(host: str, mode: Mode, temperature: int) -> None:
    p = {
        Property.STATUS: Status.ON.value,
        Property.MODE: mode.value
    }
    if temperature >= 0:
        p[Property.TEMPERATURE] = temperature.to_bytes(1, byteorder='big')
    f = create_frame(Service.SET_I, p)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(f, (host, PORT))

def print_usage_and_exit():
    print('usage: python3 ac_controller.py [ off | on | info ]')
    sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print_usage_and_exit()

    host = find_air_conditioner()
    if sys.argv[1] == 'off':
        turn_off(host)
        sys.exit()

    info = get_sensor_info(host)
    if sys.argv[1] == 'on':
        if info['htemp'] <= 20:
            turn_on(host, Mode.HEATING, 22)
        elif info['htemp'] >= 28 and info['otemp'] >= 25:
            turn_on(host, Mode.COOLING, 26)
        elif info['hhum'] >= 70 and info['otemp'] >= 25:
            turn_on(host, Mode.DEHUMIDIFICATION, -1)
        sys.exit()

    print(info)
