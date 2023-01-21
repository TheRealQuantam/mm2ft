# makeftrom.py
# Copyright 2022 Justin Olbrantz (Quantam)

# Script to build an mm2ft project with custom music.
# See readme.txt for usage instructions.

# This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License. To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import bisect
import collections as colls
import configparser
from ctypes import *
from enum import Enum, IntEnum, IntFlag, auto
import errno
import famitrackerbinary as ftbin
import filecmp
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

rom_size = 512 * 1024 + 16
bank_size = 0x2000

tbl_bank = 0x18
c2_track_tbl_offs = 0xa50
mst_track_tbl_offs = 0xad6

first_free_bank = 0x20
end_free_bank = 0x3e
music_bank_addr = 0xa000

dpcm_bank = 0x3f
dpcm_bank_base_addr = 0xe000
dpcm_addr = 0xf300
max_dpcm_size = 0x600

track_names = (
	"FlashMan", # 0
	"WoodMan", # 1
	"CrashMan", # 2
	"HeatMan", # 3
	"AirMan", # 4
	"MetalMan", # 5
	"QuickMan", # 6
	"BubbleMan", # 7
	"Wily1", # 8
	"Wily3", # 9
	"StageSelected", # a
	"Boss", # b
	"StageSelect", # c
	"Title", # d
	"Intro", # e
	"GameOver", # f
	"Password", # 10
	"WilyCastle", # 11
	"WilyCapsule", # 12
	"Ending", # 13
	"Credits", # 14
	"StageClear", # 15
	"GameClear", # 16
	"GetWeapon", # 17
	"Wily2", # 18
	"Wily4", # 19
	"Wily5", # 1a
	"Wily6", # 1b
	"Track1c", # 1c
	"Track1d", # 1d
	"Track1e", # 1e
	"Track1f", # 1f
	"Track20", # 20
)
track_nums = {name: idx for idx, name in enumerate(track_names)}

c_uint16_le = c_uint16.__ctype_le__

def eprint(msg, *args, **kwargs):
	print(msg, *args, **kwargs, file = sys.stderr)

def feprint(msg, exit_code, *args, **kwargs):
	print(msg, *args, **kwargs, file = sys.stderr)
	sys.exit(exit_code)

class FatalError(Exception):
	pass

class WrappedFatalError(FatalError):
	def __init__(self, err):
		super().__init__(err)

	def __str__(self):
		return str(self.args[0])

	def __repr__(self):
		return repr(self.args[0])

def leca(bank, addr_or_offs, base_addr = None):
	offs = addr_or_offs - base_addr if base_addr is not None else addr_or_offs
	return bank * bank_size + offs + 0x10

class MasterTrackTableEntry(LittleEndianStructure):
	_pack_ = True
	_fields_ = (
		("bank_idx", c_uint8),
		("track_idx", c_uint8),
	)

class Sections(Enum):
	General = "GENERAL"
	C2Files = "C2 FILES"
	FtFiles = "FT FILES"
	Tracks = "TRACKS"

class Keys(Enum):
	TrackDir = "TrackDir"
	InRom = "InputRom"
	OutRom = "OutputRom"
	DpcmSamples = "DpcmSamples"
	ExBanks = "ExcludeBanks"

c2_track_str_re = re.compile(r"^ ( [a-f\d]{4} ) \s* ; \s* ( .*? ) \s*", re.I | re.X)
hex_str_re = re.compile(r"( (?: [a-f\d]{2} )+ )", re.I | re.X)
hex_bin_str_re = re.compile(rb"( (?: [a-f\d]{2} )+ )", re.I | re.X)

ft_exe_names = "Dn-FamiTracker.exe".split()

FreeSpaceEntry = colls.namedtuple("FreeSpaceEntry", "bank_idx offset size")

def check_addr(addr, base_addr, size_or_data):
	if isinstance(size_or_data, int):
		size = size_or_data
	else:
		size = len(size_or_data)

	return addr >= base_addr and addr <= base_addr + size

class ConfigFile:
	def __init__(self, path, *, default_names = track_names, filter_unused = True):
		cfg = configparser.ConfigParser(
			delimiters = ("=",),
			inline_comment_prefixes = None,
			strict = True,
			empty_lines_in_values = False,
			default_section = Sections.General,
			interpolation = None,
		)
		cfg.optionxform = str

		with open(path, "rt") as file:
			cfg.read_file(file, path)

		self.cfg_path = path
		self.track_dir = None
		self.in_path = self.out_path = self.dpcm_path = None
		self.dpcm_from_ftm = False
		self.ex_banks = set()

		self._parse_general(cfg)

		self.files = {}
		self.tracks = {}

		self._parse_files(cfg, Sections.C2Files)
		self._parse_files(cfg, Sections.FtFiles)

		self._add_predef_tracks(default_names)
		self._parse_tracks(cfg)

		if filter_unused:
			self._filter_unused_files()

		return

	def _parse_general(self, cfg):
		def get(key, fallback = None):
			return cfg.get(Sections.General.value, key.value, fallback = fallback)

		self.track_dir = self.cfg_path.parent.joinpath(get(Keys.TrackDir, "."))
		src_rom = get(Keys.InRom)
		tgt_rom = get(Keys.OutRom)
		dpcm_samples = get(Keys.DpcmSamples)
		ex_banks_str = get(Keys.ExBanks, "")

		if src_rom:
			self.in_path = Path(src_rom)
		if tgt_rom:
			self.out_path = Path(tgt_rom)
		if dpcm_samples:
			self.dpcm_path = Path(dpcm_samples)

		for bank_str in filter(bool, map(str.strip, ex_banks_str.split(","))):
			if len(bank_str) >= 2 and bank_str[0] == "$":
				num = int(bank_str[1:], 16)
			else:
				num = int(bank_str)

			self.ex_banks.add(num)

		return

	def _parse_files(self, cfg, section):
		if not cfg.has_section(section.value):
			return

		is_ft = section == Sections.FtFiles

		for name_str, value in cfg.items(section.value):
			track_names = list(map(str.strip, name_str.split(",")))
			assert sum(map(len, track_names)) > 0

			base_addr = None
			if not is_ft:
				assert len(track_names) == 1 and name_str

				match = c2_track_str_re.fullmatch(value)
				assert match

				base_addr = int(match[1], 16)
				value = match[2]

				if value:
					data = None
					try:
						data = bytes.fromhex(value)

						self.tracks[name_str] = {
							"name": name_str,
							"is_ft": False,
							"base_addr": base_addr,
							"data": data,
						}

						continue

					except ValueError:
						pass # Fall through

				else:
					self.tracks[name_str] = {
						"name": name_str,
						"is_ft": False,
						"index": 0xff,
					}

					continue

			path = self.track_dir.joinpath(value)
			assert path.is_file()
			assert path not in self.files

			self.files[path] = {
				"path": path,
				"is_ft": is_ft,
				"size": path.stat().st_size,
				"tracks": track_names,
			}

			for idx, name in enumerate(track_names):
				if not name:
					continue # No name assigned

				assert name not in self.tracks
				self.tracks[name] = {
					"name": name,
					"is_ft": is_ft,
					"path": path,
					"base_addr": base_addr,
					"index": idx,
				}

		return

	def _add_predef_tracks(self, predef_names):
		for idx, name in enumerate(predef_names):
			if name in self.tracks:
				continue

			self.tracks[name] =  {
				"name": name,
				"is_ft": False,
				"index": idx,
			}

		return

	def _parse_tracks(self, cfg):
		assert cfg.has_section(Sections.Tracks.value)

		self.track_map = {}
		for tgt_name, src_name in cfg[Sections.Tracks.value].items():
			assert tgt_name in track_nums

			if src_name:
				assert src_name in self.tracks

			self.track_map[tgt_name] = src_name

		return

	def _filter_unused_files(self):
		for name in self.tracks.keys() - self.track_map.values():
			info = self.tracks.pop(name)
			path = info.get("path")

			if path:
				self.files[path]["tracks"][info["index"]] = ""

		for path, info in tuple(self.files.items()):
			if not any(info["tracks"]):
				self.files.pop(path)

		return

class FamiTrackerExporter:
	def __init__(self, exe_names = ft_exe_names):
		for path_str in ["."] + sys.path:
			path = Path(path_str)
			for exe_name in exe_names:
				exe_path = path.joinpath(exe_name)
				if exe_path.is_file():
					self._exe_path = exe_path.resolve()

					return

		raise FileNotFoundError(exe_names[0])

	def export_bin(self, path, temp_path):
		bin_path = Path(tempfile.mktemp(".bin", "mod", dir = temp_path))
		dpcm_path = Path(tempfile.mktemp(".bin", "dpcm", dir = temp_path))
		log_path = Path(tempfile.mktemp(".txt", "log", dir = temp_path))

		res = subprocess.run(
			(self._exe_path, path, "-export", bin_path, log_path, dpcm_path),
			input = b"\r\n" * 5,
			capture_output = True,
		)

		assert not res.returncode
		assert bin_path.exists()

		log = log_path.read_text()
		assert "No expansion chip" in log

		song_nums = set((int(idx) for idx in re.findall(r"^ \s* \* \s* Song \s+ ( \d+ ) :", log, re.I | re.M | re.X)))
		assert max(song_nums) + 1 == len(song_nums)
	 
		if dpcm_path.exists():
			dpcm_path = dpcm_path.resolve()
			dpcm_size = dpcm_path.stat().st_size
		else:
			dpcm_path = dpcm_size = None

		return {
			"bin_path": bin_path.resolve(),
			"bin_size": bin_path.stat().st_size,
			"num_tracks": len(song_nums),
			"dpcm_path": dpcm_path,
			"dpcm_size": dpcm_size,
		}
	
def rebase_c2_track(base_addr, new_addr, data):
	op_sizes = (2, 2, 2, 2, 4, 2, 1, 3, 2, 1)
	data = bytearray(data)
	addr_offs = new_addr - base_addr
	track_addrs = (c_uint16_le * 5).from_buffer(data, 1)
	instr_tbl_addr = track_addrs[4]

	if instr_tbl_addr == base_addr + len(data):
		pass # TODO: Throw a warning?
	elif not check_addr(instr_tbl_addr, base_addr, data):
		raise InvalidInstrumentTable(data, base_addr)

	instr_tbl_size = len(data) - (instr_tbl_addr - base_addr)
	if instr_tbl_size % 4:
		raise InvalidInstrumentTable()

	for track_idx, track_addr in enumerate(track_addrs):
		if not track_addr or track_addr == 0xffff:
			continue

		if not check_addr(track_addr, base_addr, data):
			raise InvalidAddress(track_idx, base_addr + track_idx * 2)

		track_addrs[track_idx] += addr_offs
		if track_idx >= 4:
			continue

		prev_addrs = set()
		addr_queue = {track_addr}

		while addr_queue:
			offs = addr_queue.pop() - base_addr
			done = False
			while not done:
				addr = offs + base_addr
				if addr in prev_addrs:
					break

				opcode = data[offs]

				try:
					op_size = op_sizes[opcode]
				except IndexError:
					op_size = 1

				if opcode == 4: # Loop
					tgt_addr = c_uint16_le.from_buffer(data, offs + 2)
					if not check_addr(tgt_addr.value, base_addr, data):
						raise InvalidAddress(track_idx, addr)

					addr_queue.add(tgt_addr.value)

					tgt_addr.value += addr_offs

					done = data[offs + 1] == 0

				elif opcode == 9: # End of channel
					done = True

				prev_addrs.add(addr)

				offs += op_size

	return data

def load_c2_files(file_infos, tracks):
	for info in tracks.values():
		path = info.get("path")
		if info["is_ft"] or path is None:
			continue

		file_info = file_infos.pop(path)
		assert len(file_info["tracks"]) == 1

		data = path.read_bytes()

		try:
			data = bytes.fromhex(str(data, encoding = "ascii"))
		except UnicodeError:
			pass
		except ValueError:
			pass

		info["data"] = data
		info["size"] = len(data)
		del info["path"]
		del info["index"]

	return

def cvt_ftm_files(exporter, temp_path, file_infos):
	for info in tuple(file_infos.values()):
		path = info["path"]
		if not info["is_ft"] or path.suffix.lower() == ".bin":
			continue

		ftm_info = exporter.export_bin(path, temp_path)

		ftm_dpcm_path = ftm_info.get("dpcm_path")
		if ftm_dpcm_path and ftm_dpcm_path.stat().st_size:
			if cfg.dpcm_path:
				assert filecmp.cmp(cfg.dpcm_path, ftm_dpcm_path, False)
			else:
				cfg.dpcm_path = ftm_dpcm_path
				dpcm_from_ftm = True

		info["path"] = ftm_info["bin_path"]
		info["size"] = ftm_info["bin_size"]

		assert len(info["tracks"]) <= ftm_info["num_tracks"]

	return

def place_ft_tracks(rom, file_infos, free_banks):
	free_banks = colls.deque(sorted(free_banks))

	free_spaces = []
	for path, info in file_infos.items():
		if not info["is_ft"]:
			continue

		assert free_banks

		ftm_bin = info["path"].read_bytes()
		ftm = ftbin.DnFt.Module(ftm_bin)

		assert ftm.dpcm_size <= max_dpcm_size

		ftm.change_base_addr(music_bank_addr, dpcm_addr)
		ftm_bin = ftm.binary

		bank_idx = free_banks.popleft()
		offs = leca(bank_idx, music_bank_addr, music_bank_addr)
		rom[offs:offs + len(ftm_bin)] = ftm_bin

		bytes_left = bank_size - len(ftm_bin)
		if bytes_left >= 0x80:
			free_spaces.append(FreeSpaceEntry(bank_idx, len(ftm_bin), bytes_left))

		info["bank_idx"] = bank_idx
		info["address"] = music_bank_addr

	free_spaces.sort(key = lambda x: x.size)

	for bank_idx in free_banks:
		free_spaces.append(FreeSpaceEntry(bank_idx, 0, bank_size))

	return free_spaces

def place_c2_tracks(rom, file_infos, tracks, free_spaces):
	free_sizes = [space.size for space in free_spaces]

	for name, info in tracks.items():
		if info["is_ft"]:
			continue

		data = info.get("data")
		if data:
			size = len(data)
			idx = bisect.bisect_left(free_sizes, size)
			assert idx < len(free_spaces)

			free_space = free_spaces[idx]
			bank_idx = free_space.bank_idx
			tgt_addr = free_space.offset + music_bank_addr

			data = rebase_c2_track(info["base_addr"], tgt_addr, data)

			offs = leca(bank_idx, tgt_addr, music_bank_addr)
			rom[offs:offs + size] = data

			info["bank_idx"] = bank_idx
			info["base_addr"] = tgt_addr
			info["data"] = None

			size_left = free_space.size - size
			if size_left >= 32:
				free_spaces[idx] = FreeSpaceEntry(bank_idx, free_space.offset + size, size_left)

				free_spaces.sort(key = lambda x: x.size)
				free_sizes = [space.size for space in free_spaces]

			else:
				del free_spaces[idx]
				del free_sizes[idx]

		else:
			idx = info["index"]

			info["base_addr"] = c2_track_addrs[idx]
			bank_idx = info["bank_idx"] = mst_track_tbl[idx].bank_idx

			assert bank_idx < 0x80

	return

def update_track_tables(track_nums, rom, c2_track_addrs, mst_track_tbl, file_infos, tracks, track_map):
	for tgt_name, track_name in track_map.items():
		tgt_track_idx = track_nums[tgt_name]
		bank_track_idx = 0xff

		if track_name:
			track_info = tracks[track_name]
			if track_info["is_ft"]:
				file_info = file_infos[track_info["path"]]

				bank_idx = file_info["bank_idx"] ^ 0xff
				bank_track_idx = track_info["index"]

			else:
				# Make sure this doesn't corrupt if a vanilla track is specified but the input ROM has modified that track to an FT track.
				c2_track_addrs[tgt_track_idx] = track_info["base_addr"]

				bank_idx = track_info["bank_idx"]
				bank_track_idx = tgt_track_idx

		else:
			bank_idx = tbl_bank

		mst_track_tbl[tgt_track_idx] = MasterTrackTableEntry(bank_idx, bank_track_idx)

	return

def import_dpcm(rom, path, dpcm_addr = dpcm_addr, dpcm_bank_base_addr = dpcm_bank_base_addr):
	dpcm_bin = cfg.dpcm_path.read_bytes()

	assert len(dpcm_bin) <= max_dpcm_size

	offs = leca(dpcm_bank, dpcm_addr, dpcm_bank_base_addr)
	rom[offs:offs + len(dpcm_bin)] = dpcm_bin

	return

try:
	if len(sys.argv) <= 1:
		print("Usage: makeftrom.py config_file")
		exit(1)

	try:
		exporter = FamiTrackerExporter()
	except FileNotFoundError:
		raise FatalError("Cannot find FamiTracker executable. Ensure Dn-FamiTracker.exe is in the current directory or in PYTHONPATH")

	cfg_path = Path(sys.argv[1])
	if not cfg_path.is_file():
		raise FatalError("Config file does not exist")

	cfg = ConfigFile(cfg_path)

	file_infos = cfg.files
	tracks = cfg.tracks
	track_map = cfg.track_map

	# Load the ROM
	if not cfg.in_path:
		raise FatalError("No input ROM specified in config file (InputRom)")
	elif not cfg.in_path.is_file():
		raise FatalError("Input ROM does not exist")

	if not cfg.out_path:
		raise FatalError("No output ROM specified in config file (OutputRom)")

	rom = bytearray(cfg.in_path.read_bytes())
	if len(rom) != rom_size:
		raise FatalError(f"Input ROM should be {rom_size} bytes")

	c2_track_addrs = (c_uint16_le * len(track_names)).from_buffer(rom, leca(tbl_bank, c2_track_tbl_offs))
	mst_track_tbl = (MasterTrackTableEntry * len(track_names)).from_buffer(rom, leca(tbl_bank, mst_track_tbl_offs))

	with tempfile.TemporaryDirectory(prefix = "makeftrom") as temp_dir:
		temp_path = Path(temp_dir)

		cvt_ftm_files(exporter, temp_path, file_infos)

		load_c2_files(file_infos, tracks)

		# Import DPCM
		if cfg.dpcm_path:
			import_dpcm(rom, cfg.dpcm_path)

		free_spaces = place_ft_tracks(rom, file_infos, set(range(first_free_bank, end_free_bank)) - cfg.ex_banks)

		place_c2_tracks(rom, file_infos, tracks, free_spaces)

		update_track_tables(track_nums, rom, c2_track_addrs, mst_track_tbl, file_infos, tracks, track_map)

		# Write the new ROM
		temp_out_path = temp_path.joinpath("out.nes")
		with open(temp_out_path, "wb") as file:
			file.write(rom)

		try:
			os.replace(temp_out_path, cfg.out_path)

		except OSError as e:
			if e.errno != errno.EXDEV:
				raise

			# Stupid error caused by temp and out files being on different drives
			with open(cfg.out_path, "wb") as file:
				file.write(rom)
		
	a = 0
	a = 0
except FatalError as e:
	feprint(f"FATAL ERROR: {e}", 1)