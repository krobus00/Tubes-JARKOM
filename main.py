#!/usr/bin/python
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink
import os
import subprocess
import time


def wirteSysctl(key, value):
    """ Write kernel parameters. """
    try:
        subprocess.check_output(
            'sysctl -w {}={}'.format(key, value), shell=True)
    except:
        print("Not found")


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


class NetworkTopo(Topo):

    def build(self, **_opts):
        # add router r1-r4
        r1 = self.addNode('r1', cls=LinuxRouter, ip='192.168.1.1/24')
        r2 = self.addNode('r2', cls=LinuxRouter, ip='192.168.3.1/24')
        r3 = self.addNode('r3', cls=LinuxRouter, ip='192.168.1.2/24')
        r4 = self.addNode('r4', cls=LinuxRouter, ip='192.168.3.2/24')
        # add host ha & hb
        ha = self.addHost('ha', ip='192.168.10.2/24',
                          defaultRoute='via 192.168.10.1')
        hb = self.addHost('hb', ip='192.168.17.2/24',
                          defaultRoute='via 192.168.17.1')
        # add links

        # router - router
        # 20, 40, 60 dan 100
        max_size = 20
        self.addLink(r1, r3, cls=TCLink, max_queue_size=max_size, intfName1='r1-eth1', intfName2='r3-eth1',
                     params1={'ip': '192.168.1.1/24'}, params2={'ip': '192.168.1.2/24'}, bw=0.5)
        self.addLink(r1, r4, cls=TCLink, max_queue_size=max_size, intfName1='r1-eth2', intfName2='r4-eth1',
                     params1={'ip': '192.168.2.1/24'}, params2={'ip': '192.168.2.2/24'}, bw=1)
        self.addLink(r2, r4, cls=TCLink, max_queue_size=max_size, intfName1='r2-eth1', intfName2='r4-eth2',
                     params1={'ip': '192.168.3.1/24'}, params2={'ip': '192.168.3.2/24'}, bw=0.5)
        self.addLink(r2, r3, cls=TCLink, max_queue_size=max_size, intfName1='r2-eth2', intfName2='r3-eth2',
                     params1={'ip': '192.168.4.1/24'}, params2={'ip': '192.168.4.2/24'}, bw=1)
        # router - host
        self.addLink(ha, r1, cls=TCLink, max_queue_size=max_size, intfName2='r1-eth3',
                     params1={'ip': '192.168.10.2/24'}, params2={'ip': '192.168.10.1/24'}, bw=1)
        self.addLink(ha, r2, cls=TCLink, max_queue_size=max_size, intfName2='r2-eth3',
                     params1={'ip': '192.168.11.2/24'}, params2={'ip': '192.168.11.1/24'}, bw=1)

        self.addLink(hb, r3, cls=TCLink, max_queue_size=max_size, intfName2='r3-eth3',
                     params1={'ip': '192.168.17.2/24'}, params2={'ip': '192.168.17.1/24'}, bw=1)
        self.addLink(hb, r4, cls=TCLink, max_queue_size=max_size, intfName2='r4-eth3',
                     params1={'ip': '192.168.18.2/24'}, params2={'ip': '192.168.18.1/24'}, bw=1)


def run():
    topo = NetworkTopo()
    net = Mininet(topo=topo)
    net.start()
    print("*** Setup quagga")
    for router in net.hosts:
        if router.name[0] == 'r':
            # config zebra and ripd
            router.cmd(
                "zebra -f config/zebra/{0}zebra.conf -d -i /tmp/{0}zebra.pid > logs/{0}-zebra-stdout 2>&1".format(router.name))
            router.waitOutput()
            router.cmd(
                "ripd -f config/rip/{0}ripd.conf -d -i /tmp/{0}ripd.pid > logs/{0}-ripd-stdout 2>&1".format(router.name), shell=True)
            router.waitOutput()
            print("Starting zebra and rip on {}".format(router.name))
    # MPTCP ROUTING IMPLEMENTATION
    net['ha'].cmd("ip rule add from 192.168.10.2 table 1")
    net['ha'].cmd("ip rule add from 192.168.11.2 table 2")
    net['ha'].cmd(
        "ip route add 192.168.10.0/24 dev ha-eth0 scope link table 1")
    net['ha'].cmd("ip route add default via 192.168.10.1 dev ha-eth0 table 1")
    net['ha'].cmd(
        "ip route add 192.168.11.0/24 dev ha-eth1 scope link table 2")
    net['ha'].cmd("ip route add default via 192.168.11.1 dev ha-eth1 table 2")

    net['ha'].cmd(
        "ip route add default scope global nexthop via 192.168.10.1 dev ha-eth0")

    net['hb'].cmd("ip rule add from 192.168.17.2 table 1")
    net['hb'].cmd("ip rule add from 192.168.18.2 table 2")
    net['hb'].cmd(
        "ip route add 192.168.17.0/24 dev hb-eth0 scope link table 1")
    net['hb'].cmd("ip route add default via 192.168.17.1 dev hb-eth0 table 1")
    net['hb'].cmd(
        "ip route add 192.168.18.0/24 dev hb-eth1 scope link table 2")
    net['hb'].cmd("ip route add default via 192.168.18.1 dev hb-eth1 table 2")

    net['hb'].cmd(
        "ip route add default scope global nexthop via 192.168.17.1 dev hb-eth0")
    time.sleep(5)
    print("*** Connection test")
    net.pingAll()
    print("*** Bandwidth test")
    time.sleep(5)
    net['ha'].cmd('iperf -s &')
    time.sleep(1)
    net['hb'].cmdPrint('iperf -c 192.168.10.2 -i 1')
    CLI(net)
    net.stop()
    os.system("killall -9 zebra ripd")
    os.system("rm -f /tmp/*.log /tmp/*.pid logs/*")


if __name__ == '__main__':
    # wirteSysctl('net.mptcp.mptcp_enabled', 1)
    # wirteSysctl('net.mptcp.mptcp_enabled', 0)
    # wirteSysctl('net.mptcp_path_manager', "fullmesh")
    # wirteSysctl('net.mptcp_path_manager', "default")
    os.system("rm -f /tmp/*.log /tmp/*.pid logs/*")
    os.system("mn -cc")
    os.system("clear")
    setLogLevel('info')
    run()
