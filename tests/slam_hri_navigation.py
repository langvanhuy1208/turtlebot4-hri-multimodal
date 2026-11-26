#!/usr/bin/env python3
"""Compatibility entry point for the current post-arrival HRI workflow."""
import argparse
import sys
from pathlib import Path
from direct_hri_navigation import main
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True)
    args=parser.parse_args()
    sys.argv=[sys.argv[0],'--catalog',str(args.folder/'destinations.yaml'),'--output',str(args.folder/'direct_arrival')]
    main()
