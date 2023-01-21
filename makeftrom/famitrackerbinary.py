# famitrackerbinary.py
# Copyright 2022 Justin Olbrantz (Quantam)

# Module to parse a Dn-FamiTracker BIN export and rebase it.

# This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License. To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import collections as colls
from ctypes import *
from enum import Enum, IntEnum, IntFlag, auto

c_uint16_le = c_uint16.__ctype_le__

class Error(Exception):
	pass

class DataError(Error):
	def __init__(self, err_str, *args, source, offset, struct = None, field_name = None, value = None, **kwargs):
		self.xargs = {
			"err_str": err_str,
			"source": source,
			"offset": offset,
			"struct": struct,
			"field_name": field_name,
			"value": value,
		}
		self.xargs.update(kwargs)

		super().__init__(self, err_str, args, self.xargs)

	@staticmethod
	def from_field(err_str, source, struct, field_name):
		offs = None
		if source is not None:
			try:
				base_addr = addressof(source)
			except TypeError:
				base_addr = addressof(c_byte.from_buffer(source))

			offs = addressof(struct) - base_addr

		return DataError(
			err_str, 
			source = source, 
			offset = offs,
			struct = struct,
			field_name = field_name,
			value = getattr(struct, field_name),
		)

class FormatError(DataError):
	pass

class UnsupportedError(DataError):
	pass

class DnFt:
	class Header(LittleEndianStructure):
		_pack_ = True
		_fields_ = (
			("song_list", c_uint16),
			("instrument_list", c_uint16),
			("sample_list", c_uint16),
			("samples", c_uint16),
			("groove_list", c_uint16),
			("flags", c_uint8),
			("ntsc_speed", c_uint16), # Engine speed in frames/min
			("pal_speed", c_uint16),
		)

	# Flags for Header.flags
	class HeaderFlags(IntEnum):
		NoFlags = 0
		BankSwitched = 1 << 0
		OldVibrato = 1 << 1
		LinearPitch = 1 << 2

	class SongInfo(LittleEndianStructure):
		_pack_ = True
		_fields_ = (
			("frames", c_uint16),
			("frame_count", c_uint8),
			("pattern_length", c_uint8),
			("speed", c_uint8),
			("tempo", c_uint8),
			("groove_pos", c_uint8),
			("bank", c_uint8),
		)

	class DpcmInstrument(LittleEndianStructure):
		_pack_ = True
		_fields_ = (
			("pitch", c_uint8),
			("unk1", c_uint8),
			("sample_idx", c_uint8),
		)

	class Sample(LittleEndianStructure):
		_pack_ = True
		_fields_ = (
			("address", c_uint8),
			("size", c_uint8),
			("bank", c_uint8),
		)

	class InstrumentHeader(LittleEndianStructure):
		_pack_ = True
		_fields_ = (
			("type", c_uint8),
			("env_mask", c_uint8),
			# Then an array of pointers to envelopes
		)

	class InstrumentTypes(IntEnum):
		APU = 0
		Triangle = 1 # Not used
		Noise = 2 # Not used
		DPCM = 3 # Not used
		VRC6 = 4
		Sawtooth = 5 # Not used
		VRC7 = 6
		FDS = 7
		MMC5 = 8 # Not used
		N163 = 9
		S5B = 10

	Song = colls.namedtuple("Song", ("info", "frame_addrs", "frames"))
	Instrument = colls.namedtuple("Instrument", ("info", "seq_addrs"))

	class Module:
		def __init__(self, data, base_addr = 0):
			data = self._data = bytearray(data)
			self._base_addr = base_addr
			leca = self._leca = lambda addr: (addr - self._base_addr)

			hdr = self._hdr = DnFt.Header.from_buffer(data)

			prev_addr = 0
			for name, ty in DnFt.Header._fields_[:5]:
				addr = getattr(hdr, name)
				if not self._check_addr(addr):
					raise FormatError.from_field("Invalid address", data, hdr, "name")
				if addr < prev_addr:
					raise UnsupportedError.from_field("Unsupported section ordering", data, hdr, name)

			if hdr.flags & 0xfc1:
				raise UnsupportedError.from_field("Unsupported flag", data, hdr, "flags")

			self._load_songs()
			self._load_instrs()
			self._load_samples()

			# TODO: Grooves
			grooves_offs = leca(hdr.groove_list)
			if data[grooves_offs] != 0:
				raise UnsupportedError("Grooves are not supported",
					source = data,
					offset = grooves_offs,
					value = data[grooves_offs],
				)

		@property
		def binary(self):
			return bytes(self._data)

		@property
		def header(self):
			return self._hdr

		@property
		def flags(self):
			return DnFt.HeaderFlags(self._hdr.flags)

		@property
		def dpcm_size(self):
			return self._dpcm_size

		@property
		def sample_list(self):
			return self._sample_list

		@property
		def samples(self):
			return self._samples

		@property
		def instruments(self):
			return self._instrs

		@property
		def songs(self):
			return self._songs

		def change_base_addr(self, new_base, new_dpcm_base = 0xc000):
			if new_dpcm_base < 0xc000 or new_dpcm_base > 0xffc0:
				raise ValueError("change_base_addr new_dpcm_base must be between 0xc000 and 0xffc0")
			if new_dpcm_base % 0x40:
				raise ValueError("change_base_addr new_dpcm_base must be a multiple of 64")
			if new_base + self._dpcm_size > 0x10000:
				raise ValueError("change_base_addr new_base overflows address space")

			hdr = self._hdr
			delta = new_base - self._base_addr

			hdr.song_list += delta
			hdr.instrument_list += delta
			hdr.sample_list += delta
			hdr.samples += delta
			hdr.groove_list += delta

			for song_idx, song in enumerate(self._songs):
				self._song_addrs[song_idx] += delta
				song.info.frames += delta

				for frame_idx, chan_addrs in enumerate(song.frames):
					song.frame_addrs[frame_idx] += delta
					
					for chan_idx in range(len(chan_addrs)):
						chan_addrs[chan_idx] += delta

			for instr_idx, instr in enumerate(self._instrs):
				self._instr_addrs[instr_idx] += delta

				for seq_idx in range(len(instr.seq_addrs)):
					instr.seq_addrs[seq_idx] += delta

			self._base_addr = new_base
			self._leca = lambda addr: (addr - self._base_addr)

			# Now DPCM samples
			if self._samples:
				delta = (new_dpcm_base - self._dpcm_base_addr) // 0x40
				for sample in self._samples:
					sample.address += delta
			
			return

		def _check_addr(self, addr, size = 1, *, allow_null = False):
			if addr:
				offs = self._leca(addr)
				return offs >= 0 and offs + size <= len(self._data)
			else:
				return allow_null

		def _load_songs(self):
			leca = self._leca
			data = self._data
			hdr = self._hdr

			self._songs = []
			if hdr.song_list != hdr.instrument_list:
				song_tbl_offs = leca(hdr.song_list)
				first_song_addr = c_uint16_le.from_buffer(data, song_tbl_offs).value
				num_songs = (first_song_addr - hdr.song_list) // 2

				self._song_addrs = (c_uint16_le * num_songs).from_buffer(data, song_tbl_offs)

				for song_addr in self._song_addrs:
					info = DnFt.SongInfo.from_buffer(data, leca(song_addr))
				
					frame_offs = leca(info.frames)
					#first_frame_addr = c_uint16_le.from_buffer(data, frame_offs).value
					frame_addrs = (c_uint16_le * info.frame_count).from_buffer(data, frame_offs)

					if info.frame_count > 1:
						frame_end = frame_addrs[1]
						num_chans = (frame_end - frame_addrs[0]) // 2
					else:
						addrs_offs = leca(frame_addrs[0])
						chan_addrs = (c_uint16_le * ((len(data) - addrs_offs) // 2)).from_buffer(data, addrs_offs)
						num_chans = 1
						frame_end = chan_addrs[0]

						addrs_offs += 2

						while addrs_offs < frame_end:
							frame_end = min(chan_addrs[num_chans], frame_end)
							num_chans += 1
							addrs_offs += 2
					
					Frame = c_uint16_le * num_chans
					frames = []
					for frame_addr in frame_addrs:
						frame = Frame.from_buffer(data, leca(frame_addr))
						frames.append(frame)

					self._songs.append(DnFt.Song(info, frame_addrs, frames))

			else:
				self._song_addrs = ()

			return

		def _load_samples(self):
			leca = self._leca
			data = self._data
			hdr = self._hdr

			num_instrs = (hdr.samples - hdr.sample_list) // sizeof(DnFt.DpcmInstrument)
			num_samples = (hdr.groove_list - hdr.samples) // sizeof(DnFt.Sample)

			self._sample_list = (DnFt.DpcmInstrument * num_instrs).from_buffer(data, leca(hdr.sample_list))
			self._samples = (DnFt.Sample * num_samples).from_buffer(data, leca(hdr.samples))

			base_dpcm_addr = 0x10000
			end_dpcm_addr = 0xc000
			for sample in self._samples:
				base_addr = sample.address * 0x40 + 0xc000
				end_addr = base_addr + sample.size * 16 + 1

				base_dpcm_addr = min(base_dpcm_addr, base_addr)
				end_dpcm_addr = max(end_dpcm_addr, end_addr)

				if end_dpcm_addr > 0x10000:
					raise FormatError.from_field("DPCM sample overflow address space", self._data, sample, "size")

			self._dpcm_base_addr = self._dpcm_size = 0
			if base_dpcm_addr < end_dpcm_addr:
				self._dpcm_base_addr = base_dpcm_addr
				self._dpcm_size = end_dpcm_addr - base_dpcm_addr

			return

		def _load_instrs(self):
			leca = self._leca
			data = self._data
			hdr = self._hdr

			self._instrs = []
			if hdr.instrument_list != hdr.sample_list:
				instr_tbl_offs = leca(hdr.instrument_list)
				first_instr_addr = c_uint16_le.from_buffer(data, instr_tbl_offs).value
				num_instrs = (first_instr_addr - hdr.instrument_list) // 2

				self._instr_addrs = (c_uint16_le * num_instrs).from_buffer(data, instr_tbl_offs)

				for instr_idx, instr_addr in enumerate(self._instr_addrs):
					info = DnFt.InstrumentHeader.from_buffer(data, leca(instr_addr))
					seq_tbl_addr = instr_addr + sizeof(DnFt.InstrumentHeader)
					num_seqs = bin(info.env_mask).count("1")
					seq_addrs = (c_uint16_le * num_seqs).from_buffer(data, leca(seq_tbl_addr))

					self._instrs.append(DnFt.Instrument(info, seq_addrs))

			else:
				self._instr_addrs = ()

			return