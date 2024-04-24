from mininet.topo import Topo
from mininet.node import Node

class TBTopo(Topo):
    def build(self):
        
        server = self.addHost("S")
        minihost1 = self.addHost("mh1")
        minihost2 = self.addHost("mh2")
        minihost3 = self.addHost("mh3")
        minihost4 = self.addHost("mh4")
        
        SDN_switch1 = self.addSwitch("s1")
        SDN_switch2 = self.addSwitch("s2")
        SDN_switch3 = self.addSwitch("s3")
        SDN_switch4 = self.addSwitch("s4")
        SDN_switch5 = self.addSwitch("s5")
        SDN_switch6 = self.addSwitch("s6")
        
        self.addLink(server, SDN_switch1, port2 = 1)
        self.addLink(minihost1, SDN_switch6, port2 = 1)
        self.addLink(minihost2, SDN_switch6, port2 = 2)
        self.addLink(minihost3, SDN_switch6, port2 = 3)
        self.addLink(minihost4, SDN_switch6, port2 = 4)
                
        self.addLink(SDN_switch1, SDN_switch2, 2, 1)
        self.addLink(SDN_switch1, SDN_switch3, 3, 1)
        self.addLink(SDN_switch1, SDN_switch4, 4, 1)
        self.addLink(SDN_switch1, SDN_switch5, 5, 1)
        self.addLink(SDN_switch6, SDN_switch2, 5, 2)
        self.addLink(SDN_switch6, SDN_switch3, 6, 2)
        self.addLink(SDN_switch6, SDN_switch4, 7, 2)
        self.addLink(SDN_switch6, SDN_switch5, 8, 2)
        
topos = { 'TBTopo' : ( lambda: TBTopo() ) }
