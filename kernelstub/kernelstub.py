#!/usr/bin/python3

"""
 kernelstub Version 0.2

 The automatic manager for using the Linux Kernel EFI Stub to boot
 
 Copyright 2017 Ian Santopietro <isantop@gmail.com>

 Redistribution and use in source and binary forms, with or without 
 modification, are permitted provided that the following conditions are met:

 1. Redistributions of source code must retain the above copyright notice, this 
 list of conditions and the following disclaimer.

 2. Redistributions in binary form must reproduce the above copyright notice, 
 this list of conditions and the following disclaimer in the documentation and/
 or other materials provided with the distribution.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
 AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
 IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
 ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE 
 LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
 CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
 SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS 
 INTERRUPTION) HOWEVER  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
 CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
 ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE 
 POSSIBILITY OF SUCH DAMAGE.

 This program will automatically keep a copy of the Linux Kernel image and your
 initrd.img located on your EFI System Partition (ESP) on an EFI-compatible 
 system. The benefits of this approach include being able to boot Linux directly
 and bypass the GRUB bootloader in many cases, which can save 4-6 seconds during
 boot on a system with a fast drive. Please note that there are no guarantees 
 about boot time saved using this method. 
 
 For maximum safety, kernelstub recommends leaving an entry for GRUB in your 
 system's ESP and NVRAM configuration, as GRUB allows you to modify boot
 parameters per-boot, which loading the kernel directly cannot do. The only 
 other way to do this is to use an EFI shell to manually load the kernel and 
 give it parameters from the EFI Shell. You can do this by using:
 
 fs0:> vmlinuz-image initrd=EFI/path/to/initrd/stored/on/esp options
 
 kernelstub will load parameters from the /etc/default/kernelstub config file.
"""

import os, shutil
import logging
import argparse
import subprocess
import lsb_release

def run_command(command, simulate): # Run or simulate a command
    logging.debug("Running command: "  + command)
    if simulate == True:
        output = "Simulating: " + command
        return output
    else:
        return subprocess.getoutput(command)

def get_maj(path): # Get the major device number for path's filesystem
    dev = os.stat(path).st_dev
    major = os.major(dev)
    return major

def get_min(path): #get the minor device number for path's filesystem
    dev = os.stat(path).st_dev
    minor = os.minor(dev)
    return minor

def _parse_proc_partitions(): # Parse Partition names
    res = {}
    f = open("/proc/partitions", "r")
    for line in f:
        fields = line.split()
        try:
            tmaj = int(fields[0])
            tmin = int(fields[1])
            name = fields[3]
            res[(tmaj, tmin)] = name
        except:
            # just ignore parse errors in header/separator lines
            pass
    f.close()
    return res

def get_drive_name(path): # Get a drive's /dev name, eg sda
    major = get_maj(path)
    dInfo = _parse_proc_partitions()
    name = dInfo[(major, 0)]
    return name

def get_part_name(path): # get a partition's /dev name, eg sda1
    major = get_maj(path)
    minor = get_min(path)
    pInfo = _parse_proc_partitions()
    name = pInfo[(major, minor)]
    return name

def get_uuid(fs): # Get a UUID from a filesystem dev name
    command = "blkid /dev/" + fs
    blockId = run_command(command, False)
    blockList = blockId.split('\"')
    listIndex = 0
    for i in blockList:
        if str(i)[-6:-1] == " UUID":
            index = listIndex + 1
            listIndex = listIndex + 1
        else:
            listIndex = listIndex + 1
    fsUuid = str(blockList[index])
    return fsUuid

def get_os_name(lsbDict): # Get name of the current OS, eg 'Ubuntu', or None
    osName = lsbDict.get('ID', None)
    return osName

def get_os_version(lsbDict): # Get the version number, eg '16.10', or None
    osVersion = lsbDict.get('RELEASE', None)
    return osVersion

def find_os_entry(nvram, osLabel): # Locate an existing NVRAM entry
    findIndex = 0
    for i in nvram:
            if osLabel in i:
                    logging.info("Found OS Entry")
                    logging.info("OS Entry is:       " + nvram[findIndex])
                    return findIndex
            else:
                    findIndex = findIndex + 1
    return -1

def del_boot_entry(index, sim): # Delete an entry from the NVRAM
    command = "efibootmgr -B -b " + index
    return run_command(command, sim)

# Add an entry to the NVRAM with the specified opts
def add_boot_entry(device, 
                   partition, 
                   label, 
                   loader, 
                   root, 
                   initrd, 
                   cmdline, 
                   sim): 
    command = ('efibootmgr -d ' + device + ' -p ' + partition + ' -c -L "' + 
               label + '" -l ' + loader + ' -u "root=UUID=' + root + 
               ' initrd=' + initrd + ' ro ' + cmdline + '"')
    return run_command(command, sim)

def get_file_path(path, search): # Get path to file string, for copying stuff
    command = "ls " + path + search + "* | tail -1"
    return run_command(command, False)

def copy_files(src, dest, simulate): # Copy file src into dest
    if simulate == True:
        copy = ("Simulate copying " + src + " into " + dest)
        logging.info(copy)
        return True
    else:
        copy = ("Copying " + src + " into " + dest)
        logging.info(copy)
        try:
            shutil.copy(src, dest)
            return True
        except:
            logging.error("Copy failed! Things may not work...")
            raise FileOpsError("Could not copy one or more files.")
            return False

def ensure_dir(file_path): # Make sure a file exists, and make it if it doesn't
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

def check_config(path): # check if the config file exists, read it
    if os.path.isfile(path) == True:
        f = open(path, "r")
        opts = f.readline()
        f.close()
        return opts
    else:
        raise ConfigError("Missing configuration, cannot continue")
        return "InvalidConfig"

def main(): # Do the thing
    # Set up argument processing
    parser = argparse.ArgumentParser(
        description = "Automatic Kernel EFIstub manager")
    parser.add_argument("-c",
                        "--cmdline",
                        help = ("Specify the kernel boot options to use (eg. "
                                "quiet splash). Default is to read from the "
                                "config file in /etc/default/kernelstub. "
                                "Options MUST be specified either in the "
                                "config file or using this option, otherwise "
                                "no action will be taken!"))
    parser.add_argument("-l",
                        "--log", 
                        help = ("Path to the log file. Default is "
                                "/var/log/kernelstub.log"))
    parser.add_argument("-lv",
                        "--log-level",
                        help = ("Sets the information level for the log file. "
                                "Default is INFO. Valid options are DEBUG, "
                                "INFO, WARNING, ERROR, and CRITICAL."))
    parser.add_argument("-k",
                        "--kernelpath",
                        help = ("Manually specify the path to the kernel image."
                                " This is useful if kernelstub can't find your "
                                "kernel automatically."))
    parser.add_argument("-i",
                        "--initrdpath",
                        help = ("Manually specify the path to the initrd image."
                                " Similar as for -k."))
    parser.add_argument("-v",
                        "--verbose",
                        action="store_true",
                        help = ("Displays extra information about the actions "
                                "being performed. "))
    parser.add_argument("-s",
                        "--simulate",
                        action="store_true",
                        help = ("Don't actually run any commands, just "
                                "simulate them. This is useful for testing."))
    args = parser.parse_args() 
    
    # Set up logging
    if args.log_level:
        file_level = getattr(logging, args.log_level.upper(), None)
        if not isinstance(file_level, int):
            raise ValueError('Invalid log level: %s' % args.log_level)
    else:
        file_level = "INFO"
    
    if args.verbose == True:
        console_level = "INFO"
    else:
        console_level = "WARNING"
    
    if args.log:
            logFile = args.log
    else:
        logFile = "/var/log/kernelstub.log"
    logging.basicConfig(level = file_level,
                        format = ('%(asctime)s %(name)-12s '
                                  '"%(levelname)-8s %(message)s'),
                        datefmt = '%m-%d %H:%M',
                        filename = logFile,
                        filemode = 'w')
    console = logging.StreamHandler()
    console.setLevel(console_level)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    # Figure out runtime options
    if args.simulate:
        noRun = True
    else:
        noRun = False
    
    if args.kernelpath:
        linuxPath = args.kernelpath
    else:
        logging.info("No kernel specified, attempting automatic discovery")
        linuxPath = get_file_path("/boot/", "vmlinuz")
    
    if args.initrdpath:
        initrdPath = args.initrdpath
    else:
        logging.info("No initrd specified, attempting automatic discovery")
        initrdPath = get_file_path("/boot/", "initrd.img")
    
    # First check for kernel parameters. Without them, stop and fail
    if not args.cmdline:
        configPath = "/etc/default/kernelstub"
        try:
            kernelOpts = check_config(configPath)
        except ConfigError:
            error = ("cmdline was 'InvalidConfig'\n\n"
                     "This probably means that the config file doesn't exist "
                     "and you didn't specify any boot options on the command "
                     "line.\n"
                     "Create a new config file in /etc/default/kernelstub with "
                     "your required kernel parameters and rerun kernelstub "
                     "again!\n\n")
            logging.critical(error)
            raise CmdLineError("No Kernel Parameters found")
            return 3
    else:
        kernelOpts = args.cmdline
    
    # Drive and partition information
    driveName = get_drive_name("/")
    rootFs = get_part_name("/")
    espFs = get_part_name("/boot/efi")
    espNum = espFs[-1]
    rootUuid = get_uuid(rootFs)
    
    # OS information (from LSB)
    lsbDict = lsb_release.get_distro_information()
    osName = get_os_name(lsbDict)
    osVer = get_os_version(lsbDict)
    osLabel = osName + " " + osVer
    
    # NVRAM information
    nvram = run_command("efibootmgr", False).split("\n")
    entryIndex = find_os_entry(nvram, osLabel)
    orderNum = str(nvram[entryIndex])[4:8]
    
    # Directory Information
    osDirName = osName + "-kernelstub/"
    workDir = "/boot/efi/EFI/" + osDirName
    linuxName = "linux64.efi"
    linuxDest = workDir + linuxName
    initrdName = "initrd.img"
    initrdDest = workDir + initrdName
    
    ensure_dir(workDir) # Make sure the destination exists on the ESP

    # Log some helpful information, to file and optionally console
    logging.info("NVRAM entry index: " + str(entryIndex))
    logging.info("Boot Number:       " + orderNum)
    logging.info("Drive name is      " + driveName)
    logging.info("Root FS is on      " + rootFs)
    logging.info("ESP data is on     " + espFs)
    logging.info("ESP partition #:   " + espNum)
    logging.info("Root FS UUID is:   " + rootUuid)
    logging.info("OS running is:     " + osName + " " + osVer)
    logging.info("Kernel Params:     " + kernelOpts)
    
    # Do stuff
    logging.info("Now running the commands\n")
    try:
        copy_files(linuxPath, linuxDest, noRun)
    except FileOpsError:
        error = ("Could not copy the Kernel Image  into the ESP! This "
                 "indicates a very bad problem and it is unsafe to continue. "
                 "Aborting now...")
        logging.critical(error)
        return 2
    
    try:
        copy_files(initrdPath, initrdDest, noRun)
    except FileOpsError:
        error = ("Could not copy the initrd.img  into the ESP! This indicates "
                 "a very bad problem and it is unsafe to continue. Aborting "
                 "now...")
        logging.critical(error)
        return 3
    
    # Check for an existing NVRAM entry and remove it if present
    if entryIndex >= 0:
        logging.info("Deleting old boot entry")
        logging.info("New NVRAM:\n\n" + del_boot_entry(orderNum, noRun) + "\n")
    else:
        logging.info("No old entry to remove, skipping.")
    logging.info("New NVRAM:\n\n" + add_boot_entry("/dev/" + driveName, 
                                                   espNum, 
                                                   osLabel, 
                                                   "/EFI/" + osDirName + linuxName,
                                                   rootUuid, 
                                                   "EFI/" + osDirName + initrdName,
                                                   kernelOpts,
                                                   noRun) + "\n")
    
    try:
        copy_files("/proc/cmdline", workDir + "cmdline.txt", noRun)
    except FileOpsError:
        error = ("Could not copy the current Kernel Command line into the ESP. "
                 "You should manually copy the contents of /proc/cmdline into "
                 "the ESP to ensure you can get to it in an emergency. This is "
                 "a non-critical error, so continuing without it.")
        logging.warning(error)
        pass
    return 0

if __name__ == '__main__':
    main()