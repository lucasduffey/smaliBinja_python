from binaryninja import *
from dexFile import DexFile
import struct
import traceback
import hashlib # to validate SHA1 signature
import zlib # to validate adler32 checksum
import os

DEX_MAGIC = "dex\x0a035\x00"

'''
OPCODES NEEDED
* B3
'''


# ~/binaryninja/binaryninja /home/noot/CTF/tmp/classes2.dex
	# they already did it https://gist.github.com/ezterry/1239615

#
# WARNING: dex file format changes constantly...
#

# style guideline: https://google.github.io/styleguide/pyguide.html
# 010Editor: https://github.com/strazzere/010Editor-stuff/blob/master/Templates/DEXTemplate.bt
# export PYTHONPATH=$PYTHONPATH:$HOME/binaryninja/python

# https://source.android.com/devices/tech/dalvik/dalvik-bytecode.html


# style guideline: https://google.github.io/styleguide/pyguide.html
# export PYTHONPATH=$PYTHONPATH:$HOME/binaryninja/python

# https://source.android.com/devices/tech/dalvik/dalvik-bytecode.html
# https://source.android.com/devices/tech/dalvik/instruction-formats.html
# http://pallergabor.uw.hu/androidblog/dalvik_opcodes.html

# TODO: verify accuracy - http://pallergabor.uw.hu/androidblog/dalvik_opcodes.html
# the "None" ones - are ones I didn't feel like copy-pasting
InstructionNames = [
	"nop", "move", "move/from16", "move/16", "move-wide", "move-wide/from16", "move-wide/16", "move-object", "move-object/from16", # 0x00
	"move-object/16", "move-result", "move-result-wide", "move-result-object", "move-exception", "return-void", "return", "return-wide", # 0x8
	"return-object", "const/4", "const/16", "const", "const/high16", "const-wide/16", "const-wide/32", "const-wide", "const-wide/high16"
	"const-string", "const-string-jumbo", "const-class", "monitor-enter", "monitor-exit", "check-cast", "instance-of", "array-length",
	"new-instance", "new-array", "filled-new-array", None, None, None, "throw", "goto", None, None, None, None, None

	# etc.. there are a LOT
]

RegisterNames = [
	"v0", # I believe 0 == v0
	"v1",
	"v2",
	"v3",
	"v4",
	"v5",
	"v8", # last one I saw that seems to map "X" to vX - but it makes sense to go to v15 since 0xF is max
	"v9",
	"v10", # 0xa
	"v11", # 0xB
	"v12", # 0xC
	"v13", # 0xD
	"v14", # 0xE
	"v15",  # 0xF

	# EXTENDED registers
	"v16",
	"v17",
	"v18",
	"v19",
	"v20",
	"v21",
	"v22",
	"v23",
	"v24",
	"v25",

]

NONE = 0
MOVE = 1
MOVE_FROM16 = 2
MOVE_16 = 3
MOVE_WIDE = 4
MOVE_WIDE_FROM_16 = 5
MOVE_WIDE_16 = 6
MOVE_OBJECT = 7
MOVE_OBJECT_FROM_16 = 8
MOVE_OBJECT_16 = 9
MOVE_RESULT = 10
MOVE_RESULT_WIDE = 11
MOVE_RESULT_OBJECT = 12
MOVE_EXCEPTION = 13
RETURN_VOID = 14
RETURN = 15
RETURN_WIDE = 16
RETURN_OBJECT = 17
CONST_4 = 18
CONST_16 = 19
CONST = 20
CONST_HIGH16 = 21
CONST_WIDE16 = 22

InstructionOperandTypes = [
	NONE, MOVE,

	# FIXME TODO
	MOVE_FROM16,
	MOVE_16,
	MOVE_WIDE,
	MOVE_WIDE_FROM_16,
	MOVE_WIDE_16,
	MOVE_OBJECT,
	MOVE_OBJECT_FROM_16,
	MOVE_OBJECT_16,
	MOVE_RESULT,
	MOVE_RESULT_WIDE,
	MOVE_RESULT_OBJECT,
	MOVE_EXCEPTION,
	RETURN_VOID,
	RETURN,
	RETURN_WIDE,
	RETURN_OBJECT,
	CONST_4,
	CONST_16,
	CONST,
	CONST_HIGH16,
	CONST_WIDE16,

	# FIXME TODO
	NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE,
]

OperandLengths = [
	0, # NONE - nop is either '00' or '0000' - not 100% certain
	1, # MOVE - TODO: validate/verify

	# TODO - verify
	2, # MOVE_FROM16
	2, # MOVE_16
	2, # MOVE_WIDE
	2, # MOVE_WIDE_FROM_16
	2, # MOVE_WIDE_16
	1, # MOVE_OBJECT
	2, # MOVE_OBJECT_FROM_16
	2, # MOVE_OBJECT_16
	1, # MOVE_RESULT
	1, # MOVE_RESULT_WIDE
	1, # MOVE_RESULT_OBJECT
	1, # MOVE_EXCEPTION
	1, # RETURN_VOID
	1, # RETURN
	1, # RETURN_WIDE
	1, # RETURN_OBJECT
	1, # CONST_4
	2, # CONST_16
	3, # CONST
	2, # CONST_HIGH16
	2, # CONST_WIDE16


	# TODO
	2, # TODO
	2, # TODO
	2, # TODO
	2, # TODO
	2, # TODO
	2 # TODO
]

# used for perform_get_instruction_text
OperandTokens = [
	lambda value: [], # NONE
	lambda value: [InstructionTextToken(RegisterToken, RegisterNames[value & 0xF]),
		InstructionTextToken(TextToken, ", "),
		InstructionTextToken(RegisterToken, RegisterNames[value >> 4])], # MOVE

	# MOVE_FROM16,
	lambda value: [], # TODO: actually implement....

	# MOVE_16
	lambda value: [InstructionTextToken(RegisterToken, RegisterNames[value & 0xFF]), # maybe?  - FAIL: (value >> 8), (value >> 16)
		InstructionTextToken(TextToken, ", "),
		InstructionTextToken(RegisterToken, RegisterNames[value >> 8])],

	# MOVE_WIDE
	lambda value: [], # NONE

	# MOVE_WIDE_FROM_16
	lambda value: [], # NONE

	# MOVE_WIDE_16
	lambda value: [], # NONE

	# MOVE_OBJECT
	lambda value: [], # NONE

	# MOVE_OBJECT_FROM_16
	lambda value: [], # NONE

	# MOVE_OBJECT_16
	lambda value: [], # NONE

	# MOVE_RESULT
	lambda value: [], # NONE

	# MOVE_RESULT_WIDE
	lambda value: [], # NONE

	# MOVE_RESULT_OBJECT
	lambda value: [], # NONE

	# MOVE_EXCEPTION
	lambda value: [], # NONE

	# RETURN_VOID
	lambda value: [], # NONE

	# RETURN
	lambda value: [], # NONE

	# RETURN_WIDE
	lambda value: [], # NONE

	# RETURN_OBJECT
	lambda value: [], # NONE

	# CONST_4
	lambda value: [], # NONE

	# CONST_16
	lambda value: [], # NONE

	# CONST
	lambda value: [], # NONE

	# CONST_HIGH16
	lambda value: [], # NONE

	# CONST_WIDE16
	lambda value: [] # NONE

]

InstructionIL = {
	"adc": lambda il, operand: il.set_reg(1, "a", il.add_carry(1, il.reg(1, "a"), operand, flags = "*")),
	"asl": lambda il, operand: il.store(1, operand, il.shift_left(1, il.load(1, operand), il.const(1, 1), flags = "czs")),
	"asl@": lambda il, operand: il.set_reg(1, "a", il.shift_left(1, operand, il.const(1, 1), flags = "czs")),
	"and": lambda il, operand: il.set_reg(1, "a", il.and_expr(1, il.reg(1, "a"), operand, flags = "zs")),
	"bcc": lambda il, operand: cond_branch(il, il.flag_condition(LLFC_UGE), operand),
	"bcs": lambda il, operand: cond_branch(il, il.flag_condition(LLFC_ULT), operand),
	"beq": lambda il, operand: cond_branch(il, il.flag_condition(LLFC_E), operand),
	"bit": lambda il, operand: il.and_expr(1, il.reg(1, "a"), operand, flags = "czs"),
	"bmi": lambda il, operand: cond_branch(il, il.flag("s"), operand),
	"bne": lambda il, operand: cond_branch(il, il.flag_condition(LLFC_NE), operand),
	"bpl": lambda il, operand: cond_branch(il, il.not_expr(0, il.flag("s")), operand),
	"brk": lambda il, operand: il.system_call(),
	"bvc": lambda il, operand: cond_branch(il, il.not_expr(0, il.flag("v")), operand),
	"bvs": lambda il, operand: cond_branch(il, il.flag("v"), operand),
	"clc": lambda il, operand: il.set_flag("c", il.const(0, 0)),
	"cld": lambda il, operand: il.set_flag("d", il.const(0, 0)),
	"cli": lambda il, operand: il.set_flag("i", il.const(0, 0)),
	"clv": lambda il, operand: il.set_flag("v", il.const(0, 0)),
	"cmp": lambda il, operand: il.sub(1, il.reg(1, "a"), operand, flags = "czs"),
	"cpx": lambda il, operand: il.sub(1, il.reg(1, "x"), operand, flags = "czs"),
	"cpy": lambda il, operand: il.sub(1, il.reg(1, "y"), operand, flags = "czs"),
	"dec": lambda il, operand: il.store(1, operand, il.sub(1, il.load(1, operand), il.const(1, 1), flags = "zs")),
	"dex": lambda il, operand: il.set_reg(1, "x", il.sub(1, il.reg(1, "x"), il.const(1, 1), flags = "zs")),
	"dey": lambda il, operand: il.set_reg(1, "y", il.sub(1, il.reg(1, "y"), il.const(1, 1), flags = "zs")),
	"eor": lambda il, operand: il.set_reg(1, "a", il.xor_expr(1, il.reg(1, "a"), operand, flags = "zs")),
	"inc": lambda il, operand: il.store(1, operand, il.add(1, il.load(1, operand), il.const(1, 1), flags = "zs")),
	"inx": lambda il, operand: il.set_reg(1, "x", il.add(1, il.reg(1, "x"), il.const(1, 1), flags = "zs")),
	"iny": lambda il, operand: il.set_reg(1, "y", il.add(1, il.reg(1, "y"), il.const(1, 1), flags = "zs")),
	"jmp": lambda il, operand: jump(il, operand),
	"jsr": lambda il, operand: il.call(operand),
	"lda": lambda il, operand: il.set_reg(1, "a", operand, flags = "zs"),
	"ldx": lambda il, operand: il.set_reg(1, "x", operand, flags = "zs"),
	"ldy": lambda il, operand: il.set_reg(1, "y", operand, flags = "zs"),
	"lsr": lambda il, operand: il.store(1, operand, il.logical_shift_right(1, il.load(1, operand), il.const(1, 1), flags = "czs")),
	"lsr@": lambda il, operand: il.set_reg(1, "a", il.logical_shift_right(1, il.reg(1, "a"), il.const(1, 1), flags = "czs")),
	"nop": lambda il, operand: il.nop(),
	"ora": lambda il, operand: il.set_reg(1, "a", il.or_expr(1, il.reg(1, "a"), operand, flags = "zs")),
	"pha": lambda il, operand: il.push(1, il.reg(1, "a")),
	"php": lambda il, operand: il.push(1, get_p_value(il)),
	"pla": lambda il, operand: il.set_reg(1, "a", il.pop(1), flags = "zs"),
	"plp": lambda il, operand: set_p_value(il, il.pop(1)),
	"rol": lambda il, operand: il.store(1, operand, il.rotate_left_carry(1, il.load(1, operand), il.const(1, 1), flags = "czs")),
	"rol@": lambda il, operand: il.set_reg(1, "a", il.rotate_left_carry(1, il.reg(1, "a"), il.const(1, 1), flags = "czs")),
	"ror": lambda il, operand: il.store(1, operand, il.rotate_right_carry(1, il.load(1, operand), il.const(1, 1), flags = "czs")),
	"ror@": lambda il, operand: il.set_reg(1, "a", il.rotate_right_carry(1, il.reg(1, "a"), il.const(1, 1), flags = "czs")),
	"rti": lambda il, operand: rti(il),
	"rts": lambda il, operand: il.ret(il.add(2, il.pop(2), il.const(2, 1))),
	"sbc": lambda il, operand: il.set_reg(1, "a", il.sub_borrow(1, il.reg(1, "a"), operand, flags = "*")),
	"sec": lambda il, operand: il.set_flag("c", il.const(0, 1)),
	"sed": lambda il, operand: il.set_flag("d", il.const(0, 1)),
	"sei": lambda il, operand: il.set_flag("i", il.const(0, 1)),
	"sta": lambda il, operand: il.store(1, operand, il.reg(1, "a")),
	"stx": lambda il, operand: il.store(1, operand, il.reg(1, "x")),
	"sty": lambda il, operand: il.store(1, operand, il.reg(1, "y")),
	"tax": lambda il, operand: il.set_reg(1, "x", il.reg(1, "a"), flags = "zs"),
	"tay": lambda il, operand: il.set_reg(1, "y", il.reg(1, "a"), flags = "zs"),
	"tsx": lambda il, operand: il.set_reg(1, "x", il.reg(1, "s"), flags = "zs"),
	"txa": lambda il, operand: il.set_reg(1, "a", il.reg(1, "x"), flags = "zs"),
	"txs": lambda il, operand: il.set_reg(1, "s", il.reg(1, "x")),
	"tya": lambda il, operand: il.set_reg(1, "a", il.reg(1, "y"), flags = "zs")
}

class DEXViewUpdateNotification(BinaryDataNotification):
	def __init__(self, view):
		self.view = view

	# FIXME: don't trust - pulled from NES.py
	# NOTE: when you patche and write dex code
	#	* must update checksum + signature + file size + something else?
	def data_written(self, view, offset, length):
		addr = offset - self.view.rom_offset
		while length > 0:
				bank_ofs = addr & 0x3fff
				if (bank_ofs + length) > 0x4000:
						to_read = 0x4000 - bank_ofs
				else:
						to_read = length
				if length < to_read:
						to_read = length
				if (addr >= (bank_ofs + (self.view.__class__.bank * 0x4000))) and (addr < (bank_ofs + ((self.view.__class__.bank + 1) * 0x4000))):
						self.view.notify_data_written(0x8000 + bank_ofs, to_read)
				elif (addr >= (bank_ofs + (self.view.rom_length - 0x4000))) and (addr < (bank_ofs + self.view.rom_length)):
						self.view.notify_data_written(0xc000 + bank_ofs, to_read)
				length -= to_read
				addr += to_read

	# FIXME: don't trust - pulled from NES.py
	def data_inserted(self, view, offset, length):
		self.view.notify_data_written(0x8000, 0x8000)

	# FIXME: don't trust - pulled from NES.py
	def data_removed(self, view, offset, length):
		self.view.notify_data_written(0x8000, 0x8000)


# FIXME TODO
# https://source.android.com/devices/tech/dalvik/dalvik-bytecode.html
# https://source.android.com/devices/tech/dalvik/dex-format.html
# smali is the "bytecode"
'''
registers are considered 32 bits wide. Adjacent register pairs are used for 64-bit values. There is no alignment requirement for register pairs.

The storage unit in the instruction stream is a 16-bit unsigned quantity. Some bits in some instructions are ignored / must-be-zero.
'''
class DEX(Architecture):
	name = "dex"
	address_size = 2 # TODO - doesn't seem to impact size of data in "decode_instruction"
	default_int_size = 1 # TODO
	regs = {
		# register-based, and frames are fixed in size upon creation
		"v0": RegisterInfo("v0", 1), # TODO
		"v1": RegisterInfo("v1", 1), # TODO
		"v2": RegisterInfo("v2", 1), # TODO
		"v3": RegisterInfo("v3", 1), # TODO
		"v4": RegisterInfo("v4", 1), # TODO
		"v5": RegisterInfo("v5", 1), # TODO
		"v6": RegisterInfo("v6", 1), # TODO
		"v7": RegisterInfo("v7", 1), # TODO
		"v8": RegisterInfo("v8", 1), # TODO
		"v9": RegisterInfo("v9", 1), # TODO
		"v10": RegisterInfo("v10", 1), # 0xA
		"v11": RegisterInfo("v11", 1), # 0xB
		"v12": RegisterInfo("v12", 1), # 0xC
		"v13": RegisterInfo("v13", 1), # 0xD
		"v14": RegisterInfo("v14", 1), # 0xE
		"v15": RegisterInfo("v15", 1), # 0xF

		# extended:
		# see the reg loop below this list

		# TODO: are parameter registers different than local registers (v0-v5)?
		"p0": RegisterInfo("p0", 1), # TODO
		"p1": RegisterInfo("p1", 1), # TODO
		"p2": RegisterInfo("p2", 1), # TODO

		"r13": RegisterInfo("r13", 1) # stack pointer (SP), which isn't used in dalvik
		# TODO: more
	}
	for reg in ["v16","v17","v18","v19","v20","v21","v22","v23","v24","v25"]:
		regs[reg] = RegisterInfo(reg, 1)

	stack_pointer = "r13" # TODO - no stack in dalvik? - techically R13 or SP, FIXME: this shouldn't be required by binja
	flags = ["c", "z", "i", "d", "b", "v", "s"] # TODO
	flag_write_types = ["*", "czs", "zvs", "zs"] # TODO

	def decode_instruction(self, data, addr):
		if len(data) < 1:
			return None, None, None, None
		opcode = ord(data[0])

		# temp hack - will be elimated when I fully populate InstructionNames list
		if opcode >= len(InstructionNames):
			return None, None, None, None

		instr = InstructionNames[opcode]
		if instr is None:
			return None, None, None, None

		operand = InstructionOperandTypes[opcode] # TODO

		length = 1 + OperandLengths[operand] # TODO
		log(2, "decode_instruction - opcode: %s, operand: %s, length: %s" % (str(opcode), str(operand), str(length)))

		if len(data) < length:
			return None, None, None, None

		if OperandLengths[operand] == 0:
			value = None
		#elif operand == REL:
		#	value = (addr + 2 + struct.unpack("b", data[1])[0]) & 0xffff
		elif OperandLengths[operand] == 1:
			value = ord(data[1])
		else:
			value = struct.unpack("<H", data[1:3])[0]

		# len(data) == 16, why??
		#log(2, "decode_instruction, len(data): %i" % len(data))

		print data.encode('hex')

		#value = None # for the NOP
		return instr, operand, length, value

	# first one called
	def perform_get_instruction_info(self, data, addr):
		#log(2, "perform_get_instruction_info")

		instr, operand, length, value = self.decode_instruction(data, addr)
		if instr is None:
			return None

		result = InstructionInfo()
		result.length = length

		#
		# TODO: implement jumps and other oddities
		#

		return result

	def perform_get_instruction_text(self, data, addr):
		instr, operand, length, value = self.decode_instruction(data, addr)
		if instr is None:
			return None

		# I don't think we control "InstructionTextToken"


		if operand == 3:
			print "value: ", value # it's the bytes
			print "type(value): ", type(value) # type "int"

			print "================"
			print "value >> 2: ", (value >> 2)
			print "value >> 4: ", (value >> 4)
			print "value >> 6: ", (value >> 6)
			print "value >> 8: ", (value >> 8) # pretty sure this is supposed to be first one..
			print "================"


		# FIXME: current crash
		#log(2, "perform_get_instruction_text is about to mess with tokens")
		tokens = []
		tokens.append(InstructionTextToken(TextToken, "%-7s " % instr.replace("@", ""))) # FIXME: error? this is "move" for example??
		tokens += OperandTokens[operand](value) # FIXME error: the "value" is returned from decode_instructions

		return tokens, length


		#print "================"
		#print "tokens: ", tokens
		#print "================"

		#log(2, "perform_get_instruction_text finished messing with tokens")



# see NESView Example
# pretty sure this is triggered when we do the "write" call...
# https://github.com/JesusFreke/smali/wiki/Registers
class DEXView(BinaryView, DexFile):
	name = "DEX"
	long_name = "Dalvik Executable"

	# data == BinaryView datatype
	def __init__(self, data):
		print "DEXView::__init__"
		BinaryView.__init__(self, data.file) # FIXME: is len(data.file.raw) right?

		self.data = data # FIXME: is this what we can do DexFile() on?

		raw_binary_length = len(data.file.raw)
		raw_binary = data.read(0, raw_binary_length)

		DexFile.__init__(self, raw_binary, raw_binary_length) # how do I make sure this has access to BinaryView... (to read from it)

		self.notification = DEXViewUpdateNotification(self) # TODO
		self.data.register_notification(self.notification)

		self.print_metadata() # for some reason this is getting regisered with "raw" view??

		# FIXME: it's not populating the functions...
		for class_def in self.class_defs():
			#log(2, "class_def instance")

			assert type(class_def.class_data_off) == int

			class_data_item_obj = self.class_data_item(raw_binary, class_def.class_data_off)

			# create function for each direct_method
			for direct_method in class_data_item_obj.direct_methods():
				#log(2, "direct_method instance")
				print "direct_method code_off:", direct_method["code_off"]

				# direct_method.code_off
				data.create_user_function(Architecture['dex'].standalone_platform, direct_method["code_off"]) # FIXME: failing

			# create function for each virtual_method
			for virtual_method in class_data_item_obj.virtual_methods():
				print "virtual_method code_off:", virtual_method["code_off"]

				# virtual_method.code_off
				data.create_user_function(Architecture['dex'].standalone_platform, virtual_method["code_off"]) # FIXME: failing

			print "" # for debugging only, improve readability


		# this might be a better way to do it. Just create functions
		#data.create_user_function(Architecture['dex'].standalone_platform, 0) # FAILURE TO CREATE VIEW..

	@classmethod
	def is_valid_for_data(self, data):
		print "DEXView::is_valid_for_data"

		hdr = data.read(0, 16)
		if len(hdr) < 16:
				return False
		# magic - https://en.wikipedia.org/wiki/List_of_file_signatures
		if hdr[0:8] != DEX_MAGIC: # dex file format
				return False

		return True


	def init(self):
		try:
			# TODO: look at NES.py
			self.add_entry_point(Architecture['dex'].standalone_platform, self.perform_get_entry_point())

			return True
		except:
			log_error(traceback.format_exc())
			return False



	# FIXME
	def perform_is_valid_offset(self, addr):
		if (addr >= 0x8000) and (addr < 0x10000):
				return True
		return False

	# FIXME
	def perform_read(self, addr, length):
		return "" # FIXME

		"""
				if addr < 0x8000:
						return None
				if addr >= (0x8000 ):
						return None
				if (addr + length) > 0x10000:
						length = 0x10000 - addr
				result = ""

				while length > 0:
						bank_ofs = addr & 0x3fff
						to_read = 0x4000 - bank_ofs
						data = self.data.read(bank_ofs + 0x4000), to_read)
						result += data
						if len(data) < to_read:
								break
						length -= to_read
						addr += to_read

				return result
		"""

	# FIXME
	#def perform_write(self, addr, value):
	#	pass

	# FIXME
	def perform_get_start(self):
	   #print("[perform_get_start]") # NOTE: seems to infinite loop (for both 0 or 1 return, haven't tested others)
	   return 0

	# FIXME
	def perform_get_length(self):
		return 0x10000

	def perform_is_executable(self):
		return True

	# FIXME
	def perform_get_entry_point(self):
		# complicated because this is called without self really existing
		#   * not really sure what self provides...

		#self.data = data # FIXME: is this what we can do DexFile() on?

		# FOLLOWING CODE DOENS'T WORK..
		#binary_blob_length = len(self.data.raw)
		#binary_blob = self.data.file.read(0, binary_blob_length)
		#tmp = DexFile(binary_blob, binary_blob_length) # how do I make sure this has access to BinaryView... (to read from it)

		#dataOff = tmp.dataOff()
		#fileSize = len(self.data.file.raw) # TODO: is this checking size of APK, or size of dex...

		#print "dexView::perform_get_entry_point: ", dataOff, "hex(dataOff): ", hex(dataOff), ", file size: ", fileSize

		#assert dataOff <= fileSize

		#return dataOff

		# return 0 for now, since perform_get_entry_point gets called before __init__ it overcomplicates some stuff...
		return int(0) # for some reason I frequently get "0x0 isn't valid entry point"..

print("dexView - for real")
print("test against classes2.dex - because there is actually dex code..")
class DEXViewBank(DEXView):
	name = "DEX"
	long_name = "Dalvik Executable"

	def __init__(self, data):
		DEXView.__init__(self, data)

DEXViewBank.register()
DEX.register()


# Architecture.register
