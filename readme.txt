Mega Man 2 FamiTracker Patch
v0.1

By Justin Olbrantz (Quantam)

The mm2ft patch adds FamiTracker Module playback support to Mega Man 2, both making it far easier to compose and import custom music for hacks and providing a far more powerful sound engine. This engine is added on top of the Capcom 2 sound engine used by MM2, and both C2 and FT format music may be used in a single hack.

Basic Features:
- Support for FamiTracker Modules as implemented by bhop (https://github.com/zeta0134/bhop)
	- Supports basic FT features including channel volume, instruments, volume/pitch/arpeggio/mode envelopes, true tempo, etc.
	- Supports effects 0 (arpeggio), 1/2 (pitch slide), 3 (portamento), 4 (vibrato), 7 (tremolo), A (volume slide), B (go to order), C (halt), D (go to row in next order), F (speed/tempo), G (note delay), P (fine pitch), Q/R (pitch slide to note), S (delayed cut), V (mode), Y (DPCM sample offset), Z (DPCM delta counter)
	- Supports all base (2A03) channels including DPCM
	- Does NOT support expansion chips, linear pitch mode, hi-pitch envelopes, grooves, or effects E (old-style volume), EE (toggle hardware envelope/length counter), E (length counter), H/I (hardware sweep), L (delayed release), M (delayed volume), S (set linear counter), T (transpose), W (DPCM pitch), X (DPCM retrigger)
- 1.5 KB available for DPCM samples
- Supports unique tracks for all Wily stages
- Supports stage-specific boss music, including separate refight music
- Multi-bank support for both FT and C2 music, allowing for up to 256 KB of music data and up to 8 KB per track
- Expands ROM size to 512 KB, almost half of which is available for music and other hacks
- Adds 8 KB PRG-RAM, most of which is available for other hacks
- Incorporates mm2mmc3 which converts MM2 to MMC3, fixes the delay-scroll bug, and provides a scanline interrupt timer derivative hacks may use
- Incorporates mm2scrollfix for smooth, artifact-free vertical scrolling

HOW IT WORKS

The basic principle of operation of mm2ft is simple. mm2ft runs both the original sound engine and bhop in parallel, mixing the output based on which engine is playing and which channels are currently in use by sound effects (which always use the C2 sound engine).

The hardware design of DPCM in the NES brings some additional complexity and required changes in unexpected places. The DPCM DMA can intermittently corrupt reads from various other hardware, chiefly the controller input and reading from VRAM. Working around this requires modification of both the controller read function and the various functions that read from VRAM, mainly related to tile palettes and level streaming. In fact mm2scrollfix was originally written as a part of mm2ft's solution to the DPCM DMA problems, but was ultimately split off as it is useful even without mm2ft.

CAVEATS

The 1 notable caveat of mm2ft is that it uses additional CPU as compared to the C2 sound engine. Further work needs to be done to fully understand the performance of bhop vs C2 and how FT tracks can be written to minimize CPU usage, but mm2ft typically adds about 5% total CPU usage when playing an FT track compared to playing a C2 track. This, of course, increases the amount of lag in the game. To offset this, it is recommended that the MM2 Sprite Lag Reduction patch be used as well, which more than compensates for this increase.

REQUIREMENTS

Mega Man 2 (USA):
PRG-ROM CRC32 0FCFC04D / MD5 0527A0EE512F69E08B8DB6DC97964632
File CRC32 5E268761 / MD5 8E4BC5B03FFBD4EF91400E92E50DD294
File CRC32 80E08660 / MD5 302761A666AC89C21F185052D02127D3
File CRC32 A9BD44BC / MD5 CAAEB9EE3B52839DE261FD16F93103E6

Rockman 2 support is still todo, as it locates data in slightly different places and requires a different patch.

The mm2ft patch files are in xdelta3 format, and require the xdelta3 tool from https://www.romhacking.net/utilities/928/ or http://xdelta.org/. After download the tool must be renamed to xdelta3.exe and put in the same directory as the patch files and ROM.

The music importing script requires Python 3 (exact minimum version unclear), which must be in the system PATH; this can be obtained from https://www.python.org/downloads/. It additionally requires the Dn-FamiTracker.exe file to be in the same directory, which can be obtained from https://github.com/Dn-Programming-Core-Management/Dn-FamiTracker.

PATCHING

After assembling the ROM (name it Mega Man 2 (USA).nes), xdelta3.exe, and the mm2ft files into a directory, simply run patch.bat. This will produce mm2ft.nes and mm2ftdemo.nes. mm2ft.nes is the patched version of MM2 that will be used as the base of further hacking. mm2ftdemo.nes is a demo that replaces many of MM2 tracks with various assorted FT tracks from around the web.

COMPATIBILITY

Care must be taken when combining mm2ft with other, non-music changes.

mm2ft substantially reorganizes the MM2 track data. All tracks both music and sound effects have been moved around, and divided between 8-KB banks $18, $19, and $1f. Importantly, the C2 sound engine code and global data are at the same locations as in the base game, e.g. the MM2 track table is still located at file offset 38a60 (though it is now subordinate to the master track table).

Additionally, MMC3, like most other mappers, requires the common bank(s) (addresses c000-ffff) be the final bank(s) in the ROM. As such, in addition to any specific changes, the ENTIRE 3c010-4000f file region (MMC1 bank F) has been relocated to 7c010-8000f (MMC3 banks 3e-3f). As such ANY other hack that modifies the 3c010-4000f region will not work when patched (as the patch is modifying the wrong location). However, many of these hacks should work correctly when manually applied to the proper new locations.

TODO: Rest of this section

HOW TO USE IT

The basic workflow of adding music to a hack based on mm2ft is as follows:
1. Compose the tracks in FamiTracker using the supported features listed previously
2. Bundle the tracks into modules (FTM files) of appropriate size (use export to BIN to see what the exported size will be). If DPCM is used, all modules will need to use the same set of samples.
3. Use makeftrom to import the music into the ROM

Writing the Configuration File

makeftrom gets its parameters from a config file. This allows an entire project to be rebuilt with a single command, without the need to write custom shell or batch scripts.

The basic format of the file is based on the INI format and consists of a number of key-value pairs organized into several sections. E.g.:

# Comment
[SECTION NAME]
Key 1=Value1
Key 2, Key3, Key4 = Value2

Section and key names are case-sensitive. Names may contain spaces, however names and values may not begin or end with spaces as leading/trailing whitespace is stripped; this stripping occurs both with respect to the = and dividers such as commas and semicolons.

There are 5 sections in the config file. The GENERAL section contains general configuration information. The C2 FILES and FT FILES sections list the data files to be imported in the C2 and FamiTracker Module formats, respectively, and gives each track a name that can be used in the later sections. The TRACKS section maps track names to their uses in MM2. Finally, the BOSS TRACKS section maps track names to the boss fight music for each stage.

The following track names are predefined to refer to their original tracks in MM2: FlashMan, WoodMan, CrashMan, HeatMan, AirMan, MetalMan, QuickMan, BubbleMan, Wily1, Wily3, StageSelected, Boss, StageSelect, Title, Intro, GameOver, Password, WilyCastle, WilyCapsule, Ending, Credits, StageClear, GameClear, GetWeapon, Wily2, Wily4, Wily5, Wily6, Track1c, Track1d, Track1e, Track1f, Track20. The final 5 are not used in game, and may be used for alternate boss music or other hack-specific uses.

NOTE: These predefined track names refer simply to what is at the corresponding MM2 track numbers in the input ROM. If the input ROM has already modified these tracks, the modified tracks will be used. makeftrom does NOT support input ROMs that already contain FT tracks, and for this reason it cannot be used to modify the same ROM multiple times, so keep your unmodified ROM as a base for future modifications. As such it is recommendable to NOT modify the tracks before using makeftrom at all, as makeftrom can do it for you and without confusion or mistakes.

The democfg.txt file included is the 1 used to build mm2ftdemo, and can be used as an example of a real, working config file. Though obviously without the corresponding C2 and FT files you will not be able to actually build it.

The GENERAL Section

This section contains global settings, with the following settings:

TrackDir: [OPTIONAL] The relative directory to look for tracks. This is provided for convenience, so that file paths require less typing. This path is relative to the directory makeftrom is invoked from (which is also the default), e.g. if makeftrom is run in C:\mm2ft "TrackDir = tracks" will look for tracks in C:\mm2ft\tracks. Note that this setting is NOT used for the following paths in the GENERAL section.

InputRom: The path of the ROM to be modified. This ROM must have the mm2ft patch already applied. It can have other non-mm2ft changes, but must have all the tables makeftrom modifies in the same place. Note that it is NOT modified by makeftrom, and it does NOT use the TrackDir path.

OutputRom: The path to write the modified ROM to.

DpcmSamples: [OPTIONAL] The path to the samples.bin file exported by FT, containing the DPCM samples to be used globally. If the config file does not contain this setting but contains FTM files that use DPCM, the DPCM samples will be taken from the first FTM encountered that is used (has tracks assigned to MM2 tracks). This setting is required if all FT modules are specified as BIN files and any of them use DPCM.

ExcludeBanks: [OPTIONAL] A comma-separated list of banks that are reserved (e.g. they have data for other parts of the hack) and makeftrom should not use them. Bare numbers are decimal, while hexadecimal numbers must start with a $ (e.g. 16 and $10 are the same number).

The C2 FILES Section

This section contains C2 tracks that use MM2's sound engine's native format. These tracks can typically be extracted from games using the C2 engine using a simple hex editor, though some advanced hacks of MM2 et al exploit the C2 engine in clever ways to reduce the size of the tracks in ways not supported by makeftrom.

C2 files may be provided either in hex or binary formats, and hex format can be placed directly in the config file, while binary format must be put in a separate file. As C2 data contains pointers to parts of the track, it is also necessary to specify the address the data was originally located at in the source of the track, so that makeftrom can adjust the pointers to the location it places them.

Note that some malformed C2 tracks, including several in MM2 itself (Heat Man being the most obvious), have empty instrument tables. To properly play, C2 tracks must have definitions for every instrument used in the track, including the default instrument used when the track never explicitly sets an instrument (to be entirely precise, the default instrument is used to automatically reload the instrument data after a sound effect has overwritten it); if a track has no instruments, the engine will read beyond the end of the track's data (typically the start of the next track) and interpret that as an instrument. This results in strange and unpredictable vibrato and tremolo in the malformed tracks, the exact result depending on what data coincidentally happens to follow the track data and what sound effects occur while the track is playing. In some cases the "instrument" data can be so malformed that 1 or more of the track's channels will appear to stop playing entirely following certain sound effects.

A C2 file is defined by 1 of the following (note that < and > are just used to indicate an entity, and should NOT be actually used):

TrackName = <original track address>; <hex track data>
TrackName = <original track address>; <path of file containing hex or binary data>

The paths may contain spaces but not semicolons, and they may not begin or end with whitespace. Addresses are always in hex.

The FT FILES Section

This section is almost identical to the C2 FILES section, but rather than a single track, an FT file is an FT module, which may contain multiple tracks. As such multiple track names may be given, separated by commas; if there are fewer names than tracks in the specified module, the names will be assigned starting with the first track, and any unnamed trailing tracks will not be able to be used in game. It is not permissible to have fewer tracks in a module than names assigned.

As FT always exports binaries with a base address of 0, this is assumed in makeftrom and FT file definitions do not take a track address parameter.

Thus, for example, a 2-track FT module would look like this:

TrackName1, TrackName2 = <path of FTM or BIN file>

The TRACKS Section

Finally, this section assigns imported tracks to MM2 tracks for use in game. Its entries can have the forms:

MM2 Track Name = TrackName
MM2 Track Name =

The TrackName is the name of the track to be assigned, identical to the name given in the files sections. The MM2 track name is 1 of those listed at the start of the config file section (FlashMan, Wily1, etc.), and specifies which MM2 track is being assigned to. If no TrackName is specified, that MM2 track will be set to not play any music (e.g. vanilla Wily 6).

Remember that unless you assigned a track to 1 of them in the files section, all existing tracks in MM2 have names that may be used as TrackName as well, to assign a vanilla MM2 track to a different purpose. E.g.

FlashMan = HeatMan

makes the Heat Man stage music play in the Flash Man stage.

Running makeftrom

Once the config file has been written, running makeftrom is trivial. From a GUI like Windows Explorer, simply drag and drop the config file onto the makeftrom.py file. In this case the base directory for the project will be the directory the makeftrom.py file resides in.

Alternately, from the command line makeftrom can be executed by the following (assuming you have Python installed and in the system PATH):

python makeftrom.py <path of config file, in double-quotes of it contains spaces>

When it is run in this way, the base directory of the project will be whatever directory you were in when you entered the command.

Upon success makeftrom should print out nothing (Unix no-news-is-good-news philosophy)... but because FamiTracker doesn't properly handle command-line redirection it will instead spew out the results of exporting the FTM files as BINs. On failure it will at best print out an error message, at worst print out a Python traceback saying something about AssertionError for error conditions that aren't yet properly handled, which will be of no use to you but I might be able to tell you what it means.

TODO: Implement and document the BOSS TRACKS section

UNDER THE HOOD

TODO: This section will contain info for e.g. the Randomizer that needs to work with the data structures of mm2ft directly rather than using makeftrom.

BUGS

At this time only a single low-priority bug is known, and will not delay release.

- Occasionally (about 10% of the time when I was trying to reproduce it) certain sound effects will play for a frame or 2 longer than they should. Depending on the exact sound effect, this may or may not be audible at all.

FUTURE WORK

In the immediate future my work will be focused on finishing up the documentation and supporting scripts for v1.0 release. This includes at least:
- Finish this readme.txt
- Finish up makeftrom and handle all errors properly
- Adapt my personal benchmarking script for release so users can determine how much CPU is being used by different tracks

After that my plans are:
- v1.1 or such, containing both MM2 and RM2 versions, including translation into Japanese
- Integration into the Mega Man 2 Randomizer
- Fixing some issues FamiTracker has with its command-line interface that cause unwanted effects with makeftrom
- Finish with the work-in-progress universal optimizing NSF to FT converter I started on with the intent of allowing automatic importing of any NES track to FT. The existing NSF Importer tool sometimes works, but because its output is fully baked the resulting modules often exceed the 8 KB hard limit of mm2ft, or use far more CPU to play than is actually necessary.

CREDITS

Research, reverse-engineering, and programming: Justin Olbrantz (Quantam)
Music used by the demo: cookiefonster, nicetas_c, retrotails, ZeroJanitor, others

Thanks to the NesDev and Classic Mega Man Science communities for the occasional piece of information or advice.