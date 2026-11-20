"""Process-wide Python socket boundary, installed before framework imports.

    A runtime check, not an OS sandbox. CI also supplies no provider credentials.
"""
import os
import socket
import sys

ATTEMPTS = []
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


def _deny(event, args):
    if event == "socket.getaddrinfo" or (event in {"socket.connect", "socket.sendto"}
            and args[0].family in {socket.AF_INET, socket.AF_INET6}):
        ATTEMPTS.append(event)
        raise RuntimeError("Evaluation egress is disabled")


sys.addaudithook(_deny)
