Mega Man 2 FamiTracker Patch
v0.2 (release candidate)

By Justin Olbrantz (Quantam)

The mm2ft patch adds FamiTracker Module playback support to Mega Man 2, both making it far easier to compose and import custom music for hacks and providing a far more powerful sound engine. This engine is added on top of the Capcom 2 sound engine used by MM2, and both C2 and FT format music may be used in a single hack.

Basic Features:
- Support for FamiTracker Modules as implemented by bhop (https://github.com/zeta0134/bhop)
	- Supports basic FT features including channel volume, instruments, volume/pitch/arpeggio/mode envelopes, true tempo, etc.
	- Supports effects 0 (arpeggio), 1/2 (pitch slide), 3 (portamento), 4 (vibrato), 7 (tremolo), A (volume slide), B (go to order), C (halt), D (go to row in next order), F (speed/tempo), G (note delay), P (fine pitch), Q/R (pitch slide to note), S (delayed cut), V (mode), Y (DPCM sample offset), Z (DPCM delta counter)
	- Supports all base (2A03) channels including DPCM
	- Does NOT support expansion chips, linear pitch mode, hi-pitch envelopes, or effects E (old-style volume), EE (toggle hardware envelope/length counter), E (length counter), H/I (hardware sweep), L (delayed release), M (delayed volume), S (set linear counter), T (delayed transpose), W (DPCM pitch), X (DPCM retrigger)
- 1.5 KB available for DPCM samples
- Supports unique tracks for all Wily stages
- Supports stage-specific boss music, including separate refight music
- Increases the maximum number of tracks from 33 to 128
- Multi-bank support for both FT and C2 music, allowing for up to 256 KB of music data and up to 8 KB per track
- Expands ROM size to 512 KB, almost half of which is available for music and other hacks
- Adds 8 KB PRG-RAM, most of which is available for other hacks
- Incorporates mm2mmc3 which converts MM2 to MMC3, fixes the delay-scroll bug, and provides a scanline interrupt timer derivative hacks may use
- Incorporates mm2scrollfix for smooth, artifact-free vertical scrolling

HOW IT WORKS

The basic principle of operation of mm2ft is simple. mm2ft runs both the original sound engine and bhop in parallel, mixing the output based on which engine is playing and which channels are currently in use by sound effects (which always use the C2 sound engine).

The hardware design of DPCM in the NES brings some additional complexity and required changes in unexpected places. The DPCM DMA can intermittently corrupt reads from various other hardware, chiefly the controller input and reading from VRAM. Working around this required modification of both the controller read function and the various functions that read from VRAM, mainly related to tile palettes and level streaming. In fact mm2scrollfix was originally written as a part of mm2ft's solution to the DPCM DMA problems, but was ultimately split off as it is useful even without mm2ft.

Under the hood, mm2ft adds a second track table: the track map table. This table specifies 3 key pieces of information: what ROM bank the track is in, which track index within that bank the track is (though for C2 tracks it's simply the track's index in the C2 track address table), and which engine to use to play it. The details are not relevant to most users, so it won't be described further.

CAVEATS

The 1 notable caveat of mm2ft is that it uses additional CPU as compared to the C2 sound engine. Further work needs to be done to fully understand the performance of bhop vs C2 and how FT tracks can be written to minimize CPU usage, but mm2ft typically adds about 5% total CPU usage when playing an FT track compared to playing a C2 track. This, of course, increases the amount of lag in the game. To offset this, it is recommended that the MM2 Sprite Lag Reduction patch (https://www.romhacking.net/hacks/7481/) be used as well, which more than compensates for this increase.

REQUIREMENTS

Mega Man 2 (USA):
PRG-ROM CRC32 0FCFC04D / MD5 0527A0EE512F69E08B8DB6DC97964632
File CRC32 5E268761 / MD5 8E4BC5B03FFBD4EF91400E92E50DD294
File CRC32 80E08660 / MD5 302761A666AC89C21F185052D02127D3
File CRC32 A9BD44BC / MD5 CAAEB9EE3B52839DE261FD16F93103E6

Rockman 2:
PRG-ROM CRC32 6150517C / MD5 770D55A19AE91DCAA9560D6AA7321737
File CRC32 30B91650 / MD5 055FB8DC626FB1FBADC0A193010A3E3F

The mm2ft patch files are in xdelta3 format, and require the xdelta3 tool from https://www.romhacking.net/utilities/928/ or http://xdelta.org/. After download the tool must be renamed to xdelta3.exe and put in the same directory as the patch files and ROM.

Finally, the makeftrom utility (https://github.com/TheRealQuantam/makeftrom) is used to import music. For most users it's best to simply download the executable form, which includes the Python environment and all the dependencies. Note that some of the mm2ft files (in particular the .ftcfg files) are required by makeftrom to produce mm2ft ROMs.

PATCHING

mm2ft contains two batch files: patchmm2.bat and patchrm2.bat. After assembling the ROM, xdelta3.exe, and the mm2ft files into a directory, simply drag and drop the ROM file onto the corresponding batch file. This will produce mm2ft.nes and mm2ftdemo.nes (or the rm2 versions). mm2ft.nes is the patched version of MM2 that will be used as the base of further hacking. mm2ftdemo.nes is a demo that replaces many MM2 tracks with various assorted FT tracks from around the web.

COMPATIBILITY

Care must be taken when combining mm2ft with other, non-music changes.

mm2ft substantially reorganizes the MM2 track data. All tracks both music and sound effects have been moved around, and divided between 8-KB banks $18, $19, and $1f. Importantly, the C2 sound engine code and global data are at the same locations as in the base game, e.g. the MM2 track table is still located at file offset 38a60 (though it is now subordinate to the track map table).

Additionally, MMC3, like most other mappers, requires the common banks (addresses c000-ffff) be the final banks in the ROM. As such, in addition to any specific changes, the ENTIRE 3c010-4000f file region (MMC1 bank F) has been relocated to 7c010-8000f (MMC3 banks 3e-3f). As such ANY other hack that modifies the 3c010-4000f region will not work when patched, as the patch is modifying the wrong location. However, many of these hacks should work correctly when manually applied to the proper new locations.

mm2ft/mm2mmc3/mm2scrollfix use the following ranges that were previously free (when 2 ranges are given the left is for MM2, right is for RM2):
- 3bd34-3be3b (1d4 left)
- 7f310-7f90f (DPCM area)

As well, mm2ft/mm2mmc3/mm2scrollfix free up the following ranges:
- 31c43-3200f (3cd)
- 33f06-3400f (10a)
- 38053-38060 (e)
- 7ca26-7cb1b / 7ca23-7cb18 (f6)
- 7d0e7-7d104 / 7d0e4-7d101 (1e)
- 7d1a2-7d1ee / 7d19f-7d1eb (4d)

Finally, mm2ft/mm2mmc3/mm2scrollfix substantially modify the following ranges in a way that may break compatibility:
- 38038-3804e
- 38061-38066
- 7c010-7c060
- 7c06d-7c080
- 7d09d-7d0e6 / 7d09a-7d0e3

PRODUCING DERIVATIVE HACKS

As stated, mm2ft incorporates the mm2mmc3 conversion. For information on using the API provided by mm2mmc3, see its readme (https://www.romhacking.net/hacks/7478/).

Importing tracks is done through the aforementioned makeftrom utility, and is documented in the makeftrom manual. What is necessary is the MM2-specific list of track names that can be assigned using makeftrom:
0: FlashMan
1: WoodMan
2: CrashMan
3: HeatMan
4: AirMan
5: MetalMan
6: QuickMan
7: BubbleMan
8: Wily1
9: Wily3
a: StageSelected
b: Boss
c: StageSelect
d: Title
e: Intro
f: GameOver
10: Password
11: WilyCastle
12: WilyCapsule (NOTE: must be a C2 track)
13: Ending
14: Credits
15: StageClear
16: GameClear
17: GetWeapon
18: Wily2
19: Wily4
1a: Wily5
1b: Wily6

Additionally, tracks 1c-7f are not used in the original game but can be used for boss tracks or any other purpose that may be hacked into the game. These tracks have names e.g. Track1c and Track7f.

As well, the following boss fight names may have music assigned to them in the boss_track_map section: 
FlashMan
WoodMan
CrashMan
HeatMan
AirMan
MetalMan
QuickMan
BubbleMan
Wily1
Wily2
Wily3
Wily4
Refights (used for all refights)
Wily5 (the Wily machine)
Wily6

BUGS

At this time only a single low-priority bug is known.

- Occasionally (about 10% of the time when I was trying to reproduce it) certain sound effects will play for a frame or 2 longer than they should. Depending on the exact sound effect, this may or may not be audible at all.

CREDITS

Research, reverse-engineering, and programming: Justin Olbrantz (Quantam)
Music used by the demo: cookiefonster, nicetas_c, retrotails, ZeroJanitor, others

Thanks to the NesDev and Classic Mega Man Science communities for the occasional piece of information or advice.