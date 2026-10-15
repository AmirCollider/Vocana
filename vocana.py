"""
Vocana from the command line, with your own Python (3.10 or newer):

    python vocana.py studio                      the studio in your browser
    python vocana.py script scripts/Sample.txt   render a script -> renders/Sample/
    python vocana.py say "Hello!" --mood excited
    python vocana.py kana "Hello!"               the katakana (no VOICEVOX needed)
    python vocana.py voices                      the characters of your VOICEVOX
    python vocana.py check scripts/Sample.txt    problems in a script, without rendering
    python vocana.py doctor                      what is installed
    python vocana.py ensure-deps                 install numpy + e2k into app/lib

On Windows you do not need this file: Vocana.bat, render_script.bat and
say.bat do the same with the Python that comes inside the folder.
"""

import os
import runpy
import sys

if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    launch = runpy.run_path(os.path.join(here, 'app', 'launch.py'))
    argv = sys.argv[1:]
    if argv and argv[0] not in ('ensure-deps', 'preflight', 'doctor', '-h', '--help', '--version'):
        launch['setup_path']()
        if launch['missing']() and launch['ensure_deps'](ask=True) != 0:
            sys.exit(2)
    sys.exit(launch['main'](argv))
