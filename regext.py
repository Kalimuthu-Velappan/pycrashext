from crash import register_epython_prog as rprog

from pykdump.API import *


"""

help = '''
Dump character device list example code
'''

rprog("dump_chrdevs", "Char device list",
      "-h   - list available options",
      help)


help = '''
Dump block device list example code
'''

rprog("dump_blkdevs", "Block device list",
      "-h   - list available options",
      help)

"""



help = '''
vmware's ballooning value check
'''

if (symbol_exists('balloon')):
    rprog("vmw_mem", "vmware ballooning information ",
          "-h   - list available options",
          help)


help = '''
CPU lock check
'''

rprog("lockup", "LOCKUP check",
      "-h   - list available options",
      help)


help = '''
Helper function for reverse engineering
'''

rprog("revs", "Reverse engineering helper",
      "-h    - list available options",
      help)


help = '''
cgroup information

--tg    - task group details
'''

rprog("cgroupinfo", "cgroup information",
      "-h    - list available options",
      help)