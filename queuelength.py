from time import sleep, time
from subprocess import *
import re 

default_dir = '.'
def monitor_qlen(interval_sec=0.01):
  cmd = "tc -s qdisc show dev r1-eth2"
  ret = []
  open("length.log","w").write('')
  t0 = "%f" % time()
  while 1: 
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.stdout.read()
    matches = re.findall(r"limit\s\d{2,3}",str(output))
    if len(matches) >= 1:
      t1 = "%f" % time()
      open("length.log","a").write(str(float(t1)-float(t0))+' '+matches[0][-3:]+'\n')
    sleep(interval_sec)
monitor_qlen()

