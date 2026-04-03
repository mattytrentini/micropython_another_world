"""Constants for the Another World engine."""

# Screen dimensions
SCREEN_W = 320
SCREEN_H = 200
PAGE_SIZE = SCREEN_W * SCREEN_H // 2  # 32000 bytes (4bpp, 2 pixels/byte)

NUM_PAGES = 4

# VM constants
NUM_THREADS = 64
NUM_VARIABLES = 256
CALL_STACK_DEPTH = 64

# Thread sentinel values
THREAD_INACTIVE = 0xFFFF
THREAD_KILL = 0xFFFE

# Thread states
STATE_ACTIVE = 0
STATE_PAUSED = 1

# Special page IDs
PAGE_CURRENT = 0xFE
PAGE_SWAP = 0xFF

# No palette change requested
PALETTE_NO_CHANGE = 0xFF

# Special variable (register) indices
VAR_RANDOM_SEED = 0x3C
VAR_SCREEN_NUM = 0x67
VAR_LAST_KEYCHAR = 0xDA
VAR_HERO_POS_UP_DOWN = 0xE5
VAR_MUSIC_SYNC = 0xF4
VAR_TIMER = 0xF7
VAR_SCROLL_Y = 0xF9
VAR_HERO_ACTION = 0xFA
VAR_HERO_POS_JUMP_DOWN = 0xFB
VAR_HERO_POS_LEFT_RIGHT = 0xFC
VAR_HERO_POS_MASK = 0xFD
VAR_HERO_ACTION_POS_MASK = 0xFE
VAR_PAUSE_SLICES = 0xFF

# Resource types
RT_SOUND = 0
RT_MUSIC = 1
RT_BITMAP = 2
RT_PALETTE = 3
RT_BYTECODE = 4
RT_SHAPE = 5

# Resource status
STATUS_NULL = 0
STATUS_LOADED = 1
STATUS_TOLOAD = 2

# Game parts (levels) - each entry: (palette_res, code_res, video1_res, video2_res)
GAME_PARTS = (
    (0x14, 0x15, 0x16, 0x00),  # 16000 - Copy Protection
    (0x17, 0x18, 0x19, 0x00),  # 16001 - Introduction
    (0x1A, 0x1B, 0x1C, 0x11),  # 16002 - Water
    (0x1D, 0x1E, 0x1F, 0x11),  # 16003 - Prison
    (0x20, 0x21, 0x22, 0x11),  # 16004 - Cite
    (0x23, 0x24, 0x25, 0x00),  # 16005 - Arene
    (0x26, 0x27, 0x28, 0x11),  # 16006 - Luxe
    (0x29, 0x2A, 0x2B, 0x11),  # 16007 - Final
    (0x7D, 0x7E, 0x7F, 0x00),  # 16008 - Password
    (0x7D, 0x7E, 0x7F, 0x00),  # 16009 - Password (alt)
)

PART_COPY_PROTECTION = 16000
PART_INTRO = 16001
PART_WATER = 16002
PART_PRISON = 16003
PART_CITE = 16004
PART_ARENE = 16005
PART_LUXE = 16006
PART_FINAL = 16007
PART_PASSWORD = 16008

# Password → (checkpoint value for var[0x00], target part ID)
# Decoded from the game's password validation bytecode (part 16008).
PASSWORDS = {
    "LDKD": (10, PART_WATER),
    "LBBB": (12, PART_WATER),
    "LFDB": (14, PART_WATER),
    "HTDC": (20, PART_PRISON),
    "XKCB": (24, PART_PRISON),
    "LBJC": (26, PART_PRISON),
    "CLLD": (30, PART_CITE),
    "LBKG": (31, PART_CITE),
    "XDDJ": (32, PART_CITE),
    "DGKF": (33, PART_CITE),
    "RBJK": (34, PART_CITE),
    "FXLC": (35, PART_CITE),
    "RKDH": (36, PART_CITE),
    "KRFK": (37, PART_CITE),
    "FRTX": (38, PART_CITE),
    "KLFB": (39, PART_CITE),
    "GLHH": (40, PART_CITE),
    "TTCT": (41, PART_CITE),
    "DDRX": (42, PART_CITE),
    "TBHK": (43, PART_CITE),
    "BFLX": (44, PART_CITE),
    "XJRT": (45, PART_CITE),
    "HRTB": (46, PART_CITE),
    "HBHK": (47, PART_CITE),
    "JCGB": (48, PART_CITE),
    "BRTD": (49, PART_CITE),
    "CKJL": (50, PART_ARENE),
    "LFCK": (60, PART_LUXE),
    "HHFL": (62, PART_LUXE),
    "TFBB": (64, PART_LUXE),
    "CRGB": (65, PART_LUXE),
    "TXHF": (66, PART_LUXE),
    "XXLF": (67, PART_LUXE),
    "JHJL": (68, PART_LUXE),
    "KRTD": (70, PART_FINAL),
}

# Frame timing
FRAME_HZ = 50
FRAME_MS = 1000 // FRAME_HZ  # 20ms per slice

# Condition codes for op_condJmp
COND_EQ = 0  # ==
COND_NE = 1  # !=
COND_GT = 2  # >
COND_GE = 3  # >=
COND_LT = 4  # <
COND_LE = 5  # <=

# Opcode names (for disassembler / debug)
OPCODE_NAMES = (
    "movConst",       # 0x00
    "mov",            # 0x01
    "add",            # 0x02
    "addConst",       # 0x03
    "call",           # 0x04
    "ret",            # 0x05
    "yieldTask",      # 0x06
    "jmp",            # 0x07
    "installTask",    # 0x08
    "jmpIfVar",       # 0x09
    "condJmp",        # 0x0A
    "setPalette",     # 0x0B
    "changeTasksState",  # 0x0C
    "selectPage",     # 0x0D
    "fillPage",       # 0x0E
    "copyPage",       # 0x0F
    "updateDisplay",  # 0x10
    "removeTask",     # 0x11
    "drawString",     # 0x12
    "sub",            # 0x13
    "and",            # 0x14
    "or",             # 0x15
    "shl",            # 0x16
    "shr",            # 0x17
    "playSound",      # 0x18
    "updateResources",  # 0x19
    "playMusic",      # 0x1A
)
