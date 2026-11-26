#!/usr/bin/env python3
"""Remove only this project's domain-98 simulation processes, including orphans."""
import argparse
import os
from pathlib import Path
import signal
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve',type=int,default=0)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    keep={os.getpid(),args.preserve}
    def owned():
        found=[]
        for path in Path('/proc').iterdir():
            if not path.name.isdigit() or int(path.name) in keep:continue
            try:
                env=(path/'environ').read_bytes().split(b'\0')
                if b'ROS_DOMAIN_ID=98' not in env:continue
                if not any(e.startswith(b'IGN_PARTITION=tb4_cuoiky_') for e in env):continue
                argv=(path/'cmdline').read_bytes().split(b'\0');joined=b' '.join(argv)
                binary=argv[0].decode(errors='replace')
                ros=any(a.startswith(b'/opt/ros/humble/') or a.startswith(str(root/'install').encode()) for a in argv[:2])
                python_script=(path/'cwd').resolve()==root and any(a in [b'scripts/project_session.py',b'scripts/hri_panel.py',b'scripts/gesture_recognition_node.py',b'scripts/voice_demo_ready.py',b'scripts/lab_sim_ready.py',b'scripts/slam_scan_lab.py'] for a in argv)
                venv=binary.startswith(str(root/'.venv'))
                gazebo=b'ign gazebo' in joined and (b'/worlds/' in joined or b' -g' in joined)
                runner=Path(binary).name=='bash' and any(a in [b'scripts/start_project.sh',b'scripts/resume_lab.sh',b'scripts/run_maze.sh',b'scripts/run_mapping.sh',b'scripts/run_sim.sh',b'scripts/run_slam_workflow.sh'] for a in argv[1:3])
                runner=runner or (Path(binary).name=='bash' and any(a==str(root/'scripts'/name).encode() for a in argv[1:3] for name in ('start_project.sh','resume_lab.sh','run_maze.sh','run_mapping.sh','run_sim.sh','run_slam_workflow.sh')))
                audio=Path(binary).name=='parec' and (b'TB4ContinuousVoice' in joined or b'Bai7Voice' in joined)
                if ros or python_script or venv or gazebo or runner or audio:found.append(int(path.name))
            except (OSError,ProcessLookupError):pass
        return found
    initial=owned()
    for pid in initial:
        try:os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
    time.sleep(.6)
    for pid in owned():
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
    print('Stopped owned simulation processes:',len(initial),flush=True)


if __name__=='__main__':main()
