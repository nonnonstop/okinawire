#!/usr/bin/env python3
import argparse
import pigpio
import re
import signal
import sys
import time
import ir


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

    # Start PI
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError('pigpio is unavailable')
    try:
        with ir.IrReceiver(pi, args.r, on_ir_received, args.e), \
                ir.IrTransmitter(pi, args.t) as ir_transmitter:
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
                else:
                    print('Command not found')
    finally:
        pi.stop()


if __name__ == '__main__':
    main()
