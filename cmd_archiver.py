#!/usr/bin/env python

""" LICENSE

Copyright Command Prompt, Inc.

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose, without fee, and without a written agreement
is hereby granted, provided that the above copyright notice and this
paragraph and the following two paragraphs appear in all copies.

IN NO EVENT SHALL THE COMMAND PROMPT, INC. BE LIABLE TO ANY PARTY FOR
DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING
LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION,
EVEN IF THE COMMAND PROMPT, INC. HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.

THE COMMAND PROMPT, INC. SPECIFICALLY DISCLAIMS ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE. THE SOFTWARE PROVIDED HEREUNDER IS ON AN
"AS IS" BASIS, AND THE COMMAND PROMPT, INC. HAS NO OBLIGATIONS TO
PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.

"""


import os
import sys
import re

from ConfigParser import *
from os import *
from sys import *
from optparse import OptionParser

# Initiate command line switches

usage = "usage: %prog [options] arg1 arg2"
parser = OptionParser(usage=usage)

parser.add_option("-A", "--archive", dest="archive", action="store_true", help="Whether or not to archive")
parser.add_option("-F", "--file", dest="archivefilename", action="store", help="Archive file", metavar="FILE")
parser.add_option("-C", "--config", dest="configfilename", action="store",  help="the name of the archiver config file", metavar="FILE")
parser.add_option("-f", "--flush", dest="flush", action="store_true", help="Flush all remaining archives to slave")
parser.add_option("-P", "--push", dest="push", action="store_true", help="Push archives to remote host")

(options, args) = parser.parse_args()

archive = options.archive
archivefile = options.archivefilename
configfile = options.configfilename
flush = options.flush
push = options.push

# initiate config parser 
config = ConfigParser()
config.read(configfile)

# Set up our keys
debug = 'on'
state = config.defaults()['state']
scp_bin = config.defaults()['scp_bin']
rsync_bin = config.defaults()['rsync_bin']
protocol = config.defaults()['protocol']
slave = config.defaults()['slave']
user = config.defaults()['user']
r_archivedir = config.defaults()['r_archivedir']
l_archivedir = config.defaults()['l_archivedir']
timeout = config.defaults()['timeout']
notify_ok = config.defaults()['notify_ok']
notify_warning = config.defaults()['notify_warning']
notify_critical = config.defaults()['notify_critical']
debug = config.defaults()['debug']
pgdata = config.defaults()['pgdata']

# Let's make sure certain items can be reached

def check_config_func():  
   if protocol == 'file':
      pathvars = [l_archivedir,scp_bin,rsync_bin,pgdata,configfile]
   else:
      pathvars = [scp_bin,rsync_bin,pgdata,configfile]
   for element in pathvars:
      try:
         os.stat("%s" % (str(element)))
      except OSError, e:
         print "Config %s:  %s" % (str(element),str(e))
         exit(1)

check_config_func()

# Some command line checking

if flush:
   if configfile == None:
      parser.error("option -c is required")
      print "\n"   

if push:
   if protocol != 'file':
      parser.error("option -P requires a protocol of file")
      print "\n"

if archive:
   if configfile == None:
      parser.error("option -c is required")
   if flush:
      print "ERROR: You can not flush and archive"
      exit(1)

if debug == 'on':
   print config.defaults().keys()
   
# set up our transfer commands

if debug == 'on':
   scp_flags = "-vvv -o ConnectTimeout=%s -o StrictHostKeyChecking=no" % (str(timeout))
else:
   scp_flags = "-o ConnectTimeout=%s -o StrictHostKeyChecking=no" % (str(timeout))


def check_pgpid_func():
   pidfile = '%s/postmaster.pid' % (str(pgdata))
   try:
      check = os.stat(pidfile)
      if check:
         file = open(pidfile,'r')
         line = int(file.readline())
      sendsignal = os.kill(line,0)
      return 0
   except:
      return 1


### get_pgcontroldata_func doesn't actually do anything yet. This is more
### for archival purposes so we can remember the regex

def get_pgcontroldata_func():
   try:
      cmd = os.popen("%s %s" % (str(pgcontroldata),str(pgdata)))
      #return cmd.readlines
      for row in cmd:
         match = re.search('^Prior checkpoint location: *.{1,}' , '%s' % (str(row)))
         if match != None:
            print match
   except OSError, e:
      print
      print "Exception: %s" % (str(e))
      exit(1)

if flush:
   check = check_pgpid_func()
   if check == 0:
      print "ERROR: Can not enter flush mode if PG is already running"
      exit(1)
   scp_transfer = "%s %s %s/pg_xlog/* %s@%s:%s" % (str(scp_bin), str(scp_flags), str(pgdata), str(user), str(slave), str(r_archivedir))
   rsync_transfer = """%s %s/pg_xlog/* -e "ssh %s"  %s@%s:%s""" % (str(rsync_bin), str(pgdata), str(scp_flags), str(user), str(slave), str(r_archivedir))
   file_transfer = "rsync -au %s/pg_xlog/* %s" % (str(pgdata),str(l_archivedir))
else:
   scp_transfer = "%s %s %s %s@%s:%s" % (str(scp_bin), str(scp_flags), str(archivefile), str(user), str(slave), str(r_archivedir))
   push_transfer = """%s -azv --remove-source-files  -e "ssh %s" %s/* %s@%s:%s/""" % (str(rsync_bin), str(scp_flags), str(l_archivedir), str(user), str(slave), str(r_archivedir))
   rsync_transfer = """%s -e "ssh %s" %s %s@%s:%s""" % (str(rsync_bin), str(scp_flags), str(archivefile), str(user), str(slave), str(r_archivedir))
   file_transfer = "rsync %s/%s %s" % (str(pgdata),str(archivefile),str(l_archivedir))

def flush_check_func():
   print "\n\n"
   print "Warning! Flushing all logs will cause your slave to exit"
   print "Standby and start up. Please verify that this is exactly what you desire.\n\n"""

   print "I wish to force my slave into production: No/Yes\n\n"

   line = str(raw_input())
   if line == "Yes":
      print "Flushing all xlogs"
   elif line == "No":
      print "Exiting!"
      exit(0)
   else:
      print "Your options are Yes and No"
      exit(0)

if debug:
   if protocol == 'scp':
      print scp_transfer
   elif protocol == 'rsync':
      print rsync_transfer
   elif protocol == 'file':
      if push:
         print push_transfer
      else:
         print file_transfer

def archive_func():
      if state == 'online':
         if protocol == 'scp':
            if debug == 'on':
               print "SSH: %s " % (scp_transfer)
            retval = system("%s" % (scp_transfer))
            if retval:
               retval = system("%s %d" % (str(notify_critical), retval))
               print "Bailing out! Critical Error"
            else:
               retval = system("%s" % (str(notify_ok)))
         if protocol == 'rsync':
            if debug == 'on':
               print "RSYNC: %s " % (rsync_transfer)
            retval = system("%s" % (rsync_transfer))
            if retval:
               retval = system("%s %d" % (str(notify_critical), retval))
               print "Bailing out! Critical Error"
            else:
               retval = system("%s" % (str(notify_ok)))
         if protocol == 'file':
            if not push:
               if debug == 'on':
                  print "FILE: %s" % (file_transfer)
               try:
                  system("%s" % (file_transfer))
               except OSError, e:
                  system("%s %d" % (str(notify_critical), retval))
                  print 
                  print "Unable to copy file %s to %s " % (str(archivefile), str(l_archivedir)) 
                  print "Exception: %e" % (str(e))
                  print
            else:
               retval = system("%s" % (str(notify_ok)))
      elif state == 'offline':
         print "ARCHIVER: We are offline, queuing archives"
         system("%s" % (str(notify_warning)))
         exit(1)
      else:
         print "I must either be online or offline. There is no NULL here"
         exit(1)

def push_func():
   if protocol == 'file':
      if push:
         if debug == 'on':
            print "PUSH: %s " % (push_transfer)
            try:
               system("%s" % (push_transfer))
               system("%s" % (str(notify_ok)))
            except OSError, e:
               system("%s %d" % (str(notify_critical), retval))
               print "Bailing out! Critical Error"
               print
               print "Exception: %s" % (str(e))

if flush:
   flush_check_func()
   check_pgpid_func()
   archive_func()
elif push:
   push_func()
else:
   archive_func()

