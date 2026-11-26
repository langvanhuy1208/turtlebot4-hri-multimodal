#!/usr/bin/env python3
"""Default-maze entry point for direct commands and post-arrival buttons."""
import sys
from pathlib import Path
from direct_hri_navigation import main
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    sys.argv=[sys.argv[0],'--catalog',str(root/'maps/demo/destinations.yaml'),'--output',str(root/'results/direct_arrival_demo')]
    main()
