"""
Vocana - write plain English, hear it in any VOICEVOX character's voice.

This package is the whole program: the English-to-kana conversion, the
melody shaping, the VOICEVOX client, the script format, the renderer, the
local studio server, and the Windows installer. The batch files and
`vocana.py` at the top of the folder only find a Python and call into it.

Version numbers live here and nowhere else. The studio, the CLI, the
installer's registry entry and the update check all read VERSION.
"""

NAME = 'Vocana'
VERSION = '1.0.0'
RELEASE_DATE = '2026-10-15'
PUBLISHER = 'AmirCollider'
HOMEPAGE = 'https://amircollider.com/vocana'

# The update check reads this. It answers with the newest version and
# where to get it; nothing is sent but the GET itself (see update.py).
UPDATE_URL = 'https://amircollider.com/vocana/version.json'
