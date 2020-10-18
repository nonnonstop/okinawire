#!/usr/bin/env python3
import argparse
import pigpio
import re
import signal
import sys
import time
import ir
import sensor


def signal_handler(signum, frame):
    sys.exit(0)


def on_ir_received(result):
    print(result)


def main():
    # Set signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Parse argument
    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument(
        '-t', default=12, help='GPIO pin number of transmitter')
    arg_parser.add_argument(
        '-r', default=26, help='GPIO pin number of receiver')
    arg_parser.add_argument(
        '-e', type=float, default=0.5, help='Error rate for receiver')
    args = arg_parser.parse_args()
    arg_parser.add_argument(
        '-d', default=11, help='I2C device id')
    args = arg_parser.parse_args()

    # Start PI
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError('pigpio is unavailable')
    try:
        with ir.IrReceiver(pi, args.r, on_ir_received, args.e), \
                ir.IrTransmitter(pi, args.t) as ir_transmitter, \
                sensor.Bme680(pi, args.d) as bme680, \
                sensor.Lis3dh(pi, args.d) as lis3dh:
            bme680.apply_config(
                osrs_t=sensor.Bme680.OSRS_1,
                osrs_h=sensor.Bme680.OSRS_1,
                osrs_p=sensor.Bme680.OSRS_1,
                iir_filter=sensor.Bme680.FILTER_0,
                nb_conv=sensor.Bme680.NB_CONVS_0,
                gas_wait=200,
                heat_temp=300,
                amb_temp=25)
            lis3dh.apply_config(sensor.Lis3dh.DATA_RATE_100HZ, sensor.Lis3dh.POWER_MODE_NORMAL)
            while True:
                print('> ', end='', flush=True)
                line = sys.stdin.readline().strip()
                if not line:
                    continue
                com, _, com_arg = line.partition(' ')
                com = com.lower()
                if 'help'.startswith(com):
                    print('quit')
                    print('send nec <DATA>')
                    print('send aeha <DATA>')
                    print('get env')
                    continue
                elif 'quit'.startswith(com) or 'exit'.startswith(com):
                    return
                elif 'send'.startswith(com):
                    name, _, com_arg = com_arg.partition(' ')
                    name = name.lower()
                    if name == 'nec':
                        generator = ir.IrCodeGeneratorNec()
                    elif name == 'aeha':
                        generator = ir.IrCodeGeneratorAeha()
                    else:
                        print(f'Not supported: {name}')
                        continue
                    com_args = [int(x, 0) for x in re.sub(
                        r'[\[\]]', '', com_arg).split(',')]
                    generator.generate(com_args)
                    ir_transmitter.transmit(generator)
                    time.sleep(1)
                elif 'get'.startswith(com):
                    if com_arg == 'env':
                        temp_comp, hum_comp, press_comp, gas_res = bme680.get_data()
                        print(f"Temperature: {temp_comp} C")
                        print(f"Humidity: {hum_comp} %")
                        print(f"Pressure: {press_comp} hPa")
                        print(f"Gas resistance: {gas_res} Ohms")
                        print()
                        x, y, z = lis3dh.get_data()
                        print(f"Acceleration X: {x}")
                        print(f"Acceleration Y: {y}")
                        print(f"Acceleration Z: {z}")
                    else:
                        print(f'Not supported: {com_arg}')
                        continue
                else:
                    print('Command not found')
    finally:
        pi.stop()


if __name__ == '__main__':
    main()
