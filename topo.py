# python script to define in mininet the topology of the data plane
# as described in slide 4 of Istruzioni_Testbed.pdf

from mininet.topo import Topo
from mininet.node import Node

class TBTopo(Topo):
    def build(self):
        
        minihost1 = self.addHost("mh1")
        minihost2 = self.addHost("mh2")
        minihost3 = self.addHost("mh3")
        
        SDN_switch1 = self.addSwitch("s1")
        SDN_switch2 = self.addSwitch("s2")
        SDN_switch3 = self.addSwitch("s3")
        SDN_switch4 = self.addSwitch("s4")
        SDN_switch5 = self.addSwitch("s5")
        SDN_switch6 = self.addSwitch("s6")
        
        self.addLink(minihost1, SDN_switch2, port2 = 1)
        self.addLink(minihost2, SDN_switch3, port2 = 1)
        self.addLink(minihost3, SDN_switch6, port2 = 1)
        
        # Switch 1 
        self.addLink(SDN_switch1, SDN_switch2, 2, 2)
        self.addLink(SDN_switch1, SDN_switch4, 3, 3)
        self.addLink(SDN_switch1, SDN_switch6, 4, 4)
        # Switch 2 
        self.addLink(SDN_switch2, SDN_switch3, 3, 3)
        # Switch 3
        self.addLink(SDN_switch3, SDN_switch4, 2, 2)
        # Switch 4
        self.addLink(SDN_switch4, SDN_switch5, 1, 1)
        # Switch 5
        self.addLink(SDN_switch5, SDN_switch6, 2, 2)
        
        
topos = { 'TBTopo' : ( lambda: TBTopo() ) }