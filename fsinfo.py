"""
 Written by Daniel Sungju Kwon
"""

from __future__ import print_function
from __future__ import division

from pykdump.API import *
from LinuxDump import Tasks
import sys
import operator
import re

import crashcolor


def dentry_to_filename (dentry) :
    if (dentry == 0):
        return "<>"

    try:
        crashout = exec_crash_command ("files -d {:#x}".format(dentry))
        filename = crashout.split()[-1]
        if filename == "DIR" :
            filename = "<blank>"
        return filename
    except:
        return "<invalid>"


def get_vfsmount_from_sb(sb):
    if (sb == 0):
        return -1

    try:
        crashout_list = exec_crash_command("mount")
        for mount_line in crashout_list.splitlines():
            mount_details = mount_line.split()
            if (mount_details[1] == ("%x" % sb)):
                return int(mount_details[0], 16)
    except:
        return -1

    return -1

def get_mount_option(mnt_flags):
    return {
        0x01: "nosuid",         # "MNT_NOSUID",
        0x02: "nodev",          # "MNT_NODEV",
        0x04: "noexec",         # "MNT_NOEXEC",
        0x08: "noatime",        # "MNT_NOATIME",
        0x10: "nodiratime",     # "MNT_NODIRATIME",
        0x20: "",               # "MNT_RELATIME",
        0x40: "ro",             # "MNT_READONLY",

# Below looks too much information, so, not visible for now
#        0x100: "SHRINKABLE",
#        0x200: "WRITE_HOLD",
#        0x1000: "SHARED",
#        0x2000: "UNBINDABLE",

        0x800000: "locked",     # MNT_LOCKED
        0x8000000: "umount",    # MNT_UMOUNT
    }.get(mnt_flags, "")

def get_mount_options(mnt_flags):
    result = ""
    for x in range(0, 64):
        option = get_mount_option((mnt_flags & (1 << x)))
        if (option != "" and result != ""):
            result = result + ","
        result = result + option

    return result

def get_frozen_str(frozen_type):
    return {
        0: "SB_UNFROZEN",
        1: "SB_FREEZE_WRITE",
        2: "SB_FREEZE_PAGEFAULT",
        3: "SB_FREEZE_FS",
        4: "SB_FREEZE_COMPLETE",
        -1: "UNRECOGNIZED STATE",
    }[frozen_type]


def all_filesystem_info(options):
    super_blocks = sym2addr("super_blocks")
    for sb in readSUListFromHead(super_blocks,
                                         "s_list",
                                         "struct super_block"):
        frozen = -1
        if (member_offset('struct super_block', 's_writers') >= 0):
            frozen = sb.s_writers.frozen
        elif (member_offset('struct super_block', 's_frozen') >= 0):
            frozen = sb.s_frozen

        frozen_str = get_frozen_str(frozen)

        vfsmnt_addr = get_vfsmount_from_sb(sb)
        mnt_flags = 0
        if (vfsmnt_addr != -1):
            vfsmnt = readSU("struct vfsmount", vfsmnt_addr)
            mnt_flags = vfsmnt.mnt_flags


        if frozen_str != "SB_UNFROZEN":
            crashcolor.set_color(crashcolor.LIGHTRED)
        print ("SB: 0x%14x, frozen=%s, %s (%s) [%s], (%s)" %
               (sb, frozen_str,
               dentry_to_filename(sb.s_root), sb.s_id,
                sb.s_type.name,
                get_mount_options(mnt_flags)))
        crashcolor.set_color(crashcolor.RESET)


def find_pid_from_file(options):
    file_struct = readSU("struct file",
                         int(options.file_addr_for_pid, 16))
    d_inode = file_struct.f_path.dentry.d_inode;
    find_pid_from_inode(d_inode);


def find_pid_from_dentry(options):
    dentry = readSU("struct dentry",
                    int(options.dentry_addr_for_pid, 16))
    d_inode = dentry.d_inode;
    find_pid_from_inode(d_inode);


def find_pid_from_inode(d_inode):
    vfs_inode_offset = member_offset('struct proc_inode', 'vfs_inode');
    proc_inode = readSU("struct proc_inode", d_inode - vfs_inode_offset)
    pid_first = proc_inode.pid.tasks[0].first
    pids_offset = member_offset("struct task_struct", "pids");
    task_struct = readSU("struct task_struct", pid_first - pids_offset);

    crashout = exec_crash_command(
        "struct task_struct.pid,comm,files {:#x} -d".format(task_struct))
    print("struct task_struct.pid,comm,files %x\n%s" %
          (task_struct, crashout))

    return

O_RDONLY = 0x0
O_WRONLY = 0x1
O_RDWR = 0x2
O_ACCMODE = 0x3

def get_file_open_mode_str(f_mode):
    result_str = ""
    if ((f_mode & 0x03) == O_RDONLY):
        result_str = result_str + "Read-Only"
    if ((f_mode & 0x03) == O_WRONLY):
        result_str = result_str + "Write-Only"
    if ((f_mode & 0x03) == O_RDWR):
        result_str = result_str + "Read/Write"

    return result_str


def show_inode_details(options):
    inode = readSU("struct inode", int(options.inode, 16))
    dentry_offset = member_offset('struct dentry',
                                  'd_alias')
    i_dentry_size = member_size("struct inode", "i_dentry")
    hlist_head_sz = struct_size("struct hlist_head")
    if i_dentry_size == hlist_head_sz:
        dentry_addr = inode.i_dentry.first - dentry_offset
    else:
        dentry_addr = inode.i_dentry.next - dentry_offset

    if dentry_addr != -dentry_offset: # No dentry for this inode
        dentry = readSU('struct dentry', dentry_addr)
        dentry_details = exec_crash_command("files -d 0x%x" % (dentry))
        print(dentry_details)

    print("%s" % (get_inode_details(inode)))


def get_inode_details(inode):
    try:
        i_uid = inode.i_uid.val
        i_gid = inode.i_gid.val
    except:
        i_uid = inode.i_uid
        i_gid = inode.i_gid

    return "file size = %d bytes, ino = %d, link count = %d\n\tuid = %d, gid = %d" %\
          (inode.i_size, inode.i_ino, inode.i_nlink, i_uid, i_gid)


def show_file_details(options):
    file = readSU("struct file", int(options.file, 16))
    dentry_details = exec_crash_command("files -d 0x%x" % (file.f_path.dentry))
    print("== File Info ==")
    print(dentry_details)
    f_op_sym = exec_crash_command("sym %x" % (file.f_op))
    print("file operations = %s" % (f_op_sym), end='')
    mount_details = exec_crash_command("mount").splitlines()
    mount_str = "%x" % (file.f_path.dentry.d_sb)
    print("file open mode = %s (0x%x)" % (get_file_open_mode_str(file.f_flags), file.f_flags))
    if member_offset("struct file", "f_inode") < 0:
        f_inode = file.f_path.dentry.d_inode
    else:
        f_inode = file.f_inode
    print("%s" % (get_inode_details(f_inode)))
    print("")
    found = False
    for mount_line in mount_details:
        words = mount_line.split()
        if words[1] == mount_str:
            if found == False:
                print("== Mount Info ==")
            print(mount_line)
            found = True


def show_slab_dentry(options):
    result_lines = exec_crash_command("kmem -S dentry").splitlines()
    sb_dict = {}
    for line in result_lines:
        if line.startswith("  ["):
            dentry_addr = int(line[3:-1], 16)
            dentry   = readSU("struct dentry", dentry_addr)
            if dentry.d_sb not in sb_dict:
                sb_dict[dentry.d_sb] = 0
            sb_dict[dentry.d_sb] = sb_dict[dentry.d_sb] + 1
            if options.show_details:
                print("0x%x %s" % (dentry_addr, dentry_to_filename(dentry_addr)))

    print("\nsuberblock usage summary")
    print("=" * 30)
    print("%16s %8s %s" % ("super_block", "count", "root"))
    print("-" * 30)
    sorted_sb_dict = sorted(sb_dict.items(),
                            key=operator.itemgetter(1), reverse=True)
    total_count = 0
    for sb, count in sorted_sb_dict:
        print("0x%x %5d %s" %
              (sb, count, dentry_to_filename(sb.s_root)))
        total_count = total_count + count
    print("-" * 40)
    print("Total allocated object count = %d" % (total_count))
    print("=" * 40)


def show_caches(options):
    shrinker_list = readSymbol("shrinker_list")
    if shrinker_list == None or shrinker_list == 0:
        return

    sb_offset = member_offset("struct super_block", "s_shrink")
    if sb_offset < 0:
        return

    total_dentry_unused = 0
    total_inodes_unused = 0
    prune_super = sym2addr("prune_super")

    print("=" * 60)
    print("%18s %10s %10s %s" %\
          ("super_block", "dentries", "inodes", "path"))
    print("-" * 60)
    for shrinker in readSUListFromHead(shrinker_list,
                                       "list",
                                       "struct shrinker"):
        # Only concerns about normal super_block
        if shrinker.shrink != prune_super:
            continue

        sb = readSU("struct super_block", shrinker - sb_offset)
        dentry_unused = sb.s_nr_dentry_unused
        inodes_unused = sb.s_nr_inodes_unused
        if dentry_unused == 0 and inodes_unused == 0:
            continue
        total_dentry_unused = total_dentry_unused + dentry_unused
        total_inodes_unused = total_inodes_unused + inodes_unused

        print("0x%x %10d %10d %s" %\
              (sb, dentry_unused, inodes_unused,
               dentry_to_filename(sb.s_root)))

    print("-" * 60)
    print("%18s %10d %10d" %\
          ("Total", total_dentry_unused, total_inodes_unused))


BLOCK_SIZE_BITS = 10
BLOCKSIZE = 1 << BLOCK_SIZE_BITS

def get_uuid(s_uuid):
    result = "%0.2x%0.2x%0.2x%0.2x" % (s_uuid[0], s_uuid[1], s_uuid[2], s_uuid[3])
    result = ""
    for i in range(0, 4):
        result = result + "%0.2x" % (s_uuid[i])

    result = result + "-"
    for i in range(4, 6):
        result = result + "%0.2x" % (s_uuid[i])

    result = result + "-"
    for i in range(6, 8):
        result = result + "%0.2x" % (s_uuid[i])

    result = result + "-"
    for i in range(8, 16):
        result = result + "%0.2x" % (s_uuid[i])

    return result



def get_volume_name(s_volume_name):
    if s_volume_name.strip() == '':
        return "<none>"

    return s_volume_name


def get_attr_str(flags, flags_list, bitop=True):
    result = ""
    idx = 0
    if bitop:
        while flags > 0:
            key = 1 << idx
            if ((flags & 1) == 1) and (key in flags_list):
                result = result + flags_list[key] + " "
            idx = idx + 1
            flags = flags >> 1
    else:
        for key in flags_list:
            if (flags & key) == key:
                result = result + flags_list[key] + " "

    return result


def get_creator_os(creator_os):
    creator_os_list = {4: "lites",
                       3: "FreeBSD",
                       2: "Masix",
                       1: "Hurd",
                       0: "Linux"}
    result = get_attr_str(creator_os, creator_os_list, False)
    return result


def get_errors_behavior(s_errors):
    s_errors_list = {1: "Continue",
                     2: "Read-only",
                     3: "Panic"}
    result = get_attr_str(s_errors, s_errors_list, False)
    return result


def get_fs_state(s_state):
    fs_states_list = {0x0001: "clean",
                      0x0002: "error",
                      0x0004: "orphan"}
    result = get_attr_str(s_state, fs_states_list)
    return result


def get_default_mount_options(mount_options):
    mount_options_list = {0x00400: "journal_data",
                          0x02000: "no_uid32",
                          0x04000: "user_xattr",
                          0x08000: "acl"}
    result = get_attr_str(mount_options, mount_options_list)
    return result


def get_ext_flags(s_flags):
    s_flags_list = {0x0001: "signed_directory_hash",
                    0x0002: "unsigned_directory_hash",
                    0x0004: "test filesystem"}

    result = get_attr_str(s_flags, s_flags_list)
    return result


def get_ext4_features(ext4_super_block):
    s_feature_compat = ext4_super_block.s_feature_compat
    s_feature_incompat = ext4_super_block.s_feature_incompat
    s_feature_ro_compat = ext4_super_block.s_feature_ro_compat

    compat_list = {0x0001: "dir_prealloc",
                   0x0002: "imagic_inodes",
                   0x0004: "has_journal",
                   0x0008: "ext_attr",
                   0x0010: "resize_inode",
                   0x0020: "dir_index",
                   0x0200: "sparse_super2"}

    ro_compat_list = {0x0001: "sparse_super",
                      0x0002: "large_file",
                      0x0004: "btree_dir",
                      0x0008: "huge_file",
                      0x0010: "uninit_bg", #"gdt_csum",
                      0x0020: "dir_nlink",
                      0x0040: "extra_isize",
                      0x0100: "quota",
                      0x0200: "bigalloc"}

    incompat_list = {0x0001: "compression",
                     0x0002: "filetype",
                     0x0004: "recover",
                     0x0008: "journal_dev",
                     0x0010: "meta_bg",
                     0x0040: "extents",
                     0x0080: "64bit",
                     0x0100: "mmp",
                     0x0200: "flex_bg",
                     0x0400: "ea_inode",
                     0x1000: "dirdata",
                     0x2000: "bg_use_meta_csum",
                     0x4000: "largedir",
                     0x8000: "inline_data"}

    result = get_attr_str(s_feature_compat, compat_list)
    result = result + get_attr_str(s_feature_incompat, incompat_list)
    result = result + get_attr_str(s_feature_ro_compat, ro_compat_list)

    return result


def show_ext4_details(sb):
    try:
        ext4_sb_info = readSU("struct ext4_sb_info", sb.s_fs_info)
        ext4_super_block = readSU("struct ext4_super_block", ext4_sb_info.s_es)

        s_blocks_count = (ext4_super_block.s_blocks_count_hi << 32) +\
                        ext4_super_block.s_blocks_count_lo
        s_r_blocks_count = (ext4_super_block.s_r_blocks_count_hi << 32) +\
                        ext4_super_block.s_r_blocks_count_lo
        s_free_blocks_count = (ext4_super_block.s_free_blocks_count_hi << 32) +\
                        ext4_super_block.s_free_blocks_count_lo
        s_block_size = BLOCKSIZE << ext4_super_block.s_log_block_size
        s_frag_size = BLOCKSIZE << ext4_super_block.s_obso_log_frag_size

        print("< struct super_block 0x%x >" % sb)
        print("%-30s %s" % ("Filesystem volume name:", get_volume_name(ext4_super_block.s_volume_name)))
        print("%-30s %s" % ("Last mounted on:", ext4_super_block.s_last_mounted))
        print("%-30s %s" % ("Filesystem UUID:", get_uuid(ext4_super_block.s_uuid)))
        print("%-30s 0x%X" % ("Filesystem magic number:", sb.s_magic))
        print("%-30s %d (%s)" % ("Filesystem revision #:", ext4_super_block.s_rev_level, "dynamic" if ext4_super_block.s_rev_level > 0 else "original"))
        print("%-30s %s" % ("Filesystem features:", get_ext4_features(ext4_super_block)))
        print("%-30s %s" % ("Filesystem flags:", get_ext_flags(ext4_super_block.s_flags)))
        print("%-30s %s" % ("Default mount options:", get_default_mount_options(ext4_sb_info.s_mount_opt)))
        print("%-30s %s" % ("Filesystem state:", get_fs_state(ext4_super_block.s_state)))
        print("%-30s %s" % ("Errors behavior:", get_errors_behavior(ext4_super_block.s_errors)))
        print("%-30s %s" % ("Filesystem OS type:", get_creator_os(ext4_super_block.s_creator_os)))
        print("%-30s %d" % ("Inode count:", ext4_super_block.s_inodes_count))
        print("%-30s %d (%d KBytes)" % ("Block count:", s_blocks_count,
                                        (s_blocks_count * s_block_size) / 1024))
        print("%-30s %d (%d KBytes)" % ("Reserved block count:", s_r_blocks_count,
                                        (s_r_blocks_count * s_block_size) / 1024))
        print("%-30s %d (%d Kbytes)" % ("Free blocks:", s_free_blocks_count,
                                        (s_free_blocks_count * s_block_size) / 1024))
        print("%-30s %d" % ("Free inodes:", ext4_super_block.s_free_inodes_count))
        print("%-30s %d" % ("First block:", ext4_super_block.s_first_data_block))
        print("%-30s %d" % ("Block size:", s_block_size))
        print("%-30s %d" % ("Fragment size:", s_frag_size))
        print("%-30s %d" % ("Reserved GDT blocks:", ext4_super_block.s_reserved_gdt_blocks))
        # That's enough for now. The remaining will be implemented later if needed
    except:
        print("Can't read details for 0x%x (%s)" % (sb, dentry_to_filename(sb.s_root)), end='')
        return


def show_superblock(sb):
    fs_type = sb.s_type.name
    try:
        if fs_type == "ext4":
            show_ext4_details(sb)
            print()
    except Exception as e:
        print("Error in handling", sb)
        print(e)


def show_dumpe2fs(options):
    if options.dumpe2fs == "*":
        options.dumpe2fs = '.'

    super_blocks = sym2addr("super_blocks")
    printed = False
    for sb in readSUListFromHead(super_blocks,
                                "s_list",
                                "struct super_block"):
        mount_name = dentry_to_filename(sb.s_root)
        try:
            if re.search(options.dumpe2fs, mount_name):
                show_superblock(sb)
        except:
            if printed == False:
                print("Error occured. Please check your regular expression.")
                printed = True



def fsinfo():
    op = OptionParser()
    op.add_option("-d", "--details", dest="show_details", default=0,
                  action="store_true",
                  help="Show detailed information")
    op.add_option("-f", "--file", dest="file", default="",
                  action="store",
                  help="Show detailed file information for 'struct file' address (hex)")
    op.add_option("-i", "--inode", dest="inode", default="",
                  action="store",
                  help="Show detailed inode information for 'struct inode' address (hex)")
    op.add_option("-s", "--slab", dest="show_slab", default=0,
                  action="store_true",
                  help="Show all 'dentry' details in slab")
    op.add_option("-c", "--caches", dest="show_caches", default=0,
                  action="store_true",
                  help="Show dentry/inodes caches")
    op.add_option("--findpidbyfile", dest="file_addr_for_pid", default="",
                  action="store",
                  help="Find PID from a /proc file address (hex)")
    op.add_option("--findpidbydentry", dest="dentry_addr_for_pid",
                  default="", action="store",
                  help="Find PID from a /proc dentry address (hex)")
    op.add_option("-p", "--dumpe2fs", dest="dumpe2fs", default="",
                  action="store",
                  help="Shows dumpe2fs like information")

    (o, args) = op.parse_args()

    if (o.file_addr_for_pid != ""):
        find_pid_from_file(o)
        sys.exit(0);
    if (o.dentry_addr_for_pid != ""):
        find_pid_from_dentry(o)
        sys.exit(0);
    if (o.file != ""):
        show_file_details(o)
        sys.exit(0)
    if (o.inode != ""):
        show_inode_details(o)
        sys.exit(0)
    if (o.show_slab):
        show_slab_dentry(o)
        sys.exit(0)
    if (o.show_caches):
        show_caches(o)
        sys.exit(0)
    if (o.dumpe2fs != ""):
        show_dumpe2fs(o)
        sys.exit(0)


    all_filesystem_info(o)

if ( __name__ == '__main__'):
    fsinfo()
