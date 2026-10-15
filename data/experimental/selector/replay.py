#!/usr/bin/env python3
"""Reproduce into a new directory inside selector/ without replacing evidence."""
import argparse
from pathlib import Path
import sys

import study

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('command', choices=['prepare', 'develop', 'freeze', 'challenge', 'verify'])
parser.add_argument('--directory', default='replay')
args = parser.parse_args()
destination = (study.HERE / args.directory).resolve()
if not destination.is_relative_to(study.HERE) or destination == study.HERE:
    parser.error('directory must be a subdirectory inside selector/')
study.HERE = destination
sys.argv = [sys.argv[0], args.command]
study.main()
