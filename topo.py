# python script to define in mininet the topology of the data plane
# as described in slide 4 of Istruzioni_Testbed.pdf

from mininet.topo import Topo
from mininet.node import Node

class TBTopo(Topo):
    def build(self):
        
        h1 = self.addHost("mh1")
        h2 = self.addHost("mh2")
        h3 = self.addHost("mh3")
        
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        s4 = self.addSwitch("s4")
        s5 = self.addSwitch("s5")
        s6 = self.addSwitch("s6")
        
        self.addLink(h1, s2)
        self.addLink(h2, s3)
        self.addLink(h3, s6)
        
        # Switch 1 
        self.addLink(s1, s2)
        self.addLink(s1, s4)
        self.addLink(s1, s6)
        # Switch 2 
        self.addLink(s2, s3)
        # Switch 3
        self.addLink(s3, s4)
        # Switch 4
        self.addLink(s4, s5)
        # Switch 5
        self.addLink(s5, s6)
        
        
topos = { 'TBTopo' : ( lambda: TBTopo() ) }