#!/usr/bin/env python3
"""Mosh Server for Testbed - wraps receiver.py"""

import sys
import os
sys.path.insert(0, '/app/mosh')

from receiver import init, receive_loop

def main():
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
    print(f"[MOSH SERVER] Starting on port {UDP_PORT}")

    init(UDP_PORT)
    receive_loop()

if __name__ == "__main__":
    main()
