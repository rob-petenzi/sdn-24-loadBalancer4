from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types

class PsrSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PsrSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switch_neighbors = {}  # To store neighbors of each switch

    def get_switch_neighbors(self, dpid):
    # Define the topology-independent logic to determine neighbors
    # For simplicity, let's assume each switch is connected to all other switches
    # Modify this method based on the actual topology discovery mechanism
    return [neighbor for neighbor in self.switch_neighbors.keys() if neighbor != dpid]

@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
def switch_features_handler(self, ev):
    datapath = ev.msg.datapath
    dpid = datapath.id

    # Determine neighbors based on the discovered topology
    neighbors = self.get_switch_neighbors(dpid)
    self.switch_neighbors[dpid] = neighbors

    # Install default flow entries for unknown traffic
    self.install_default_flow(datapath)

def install_default_flow(self, datapath):
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser

    # Table 0: Send packets to controller for unknown source addresses
    match = parser.OFPMatch()
    actions = [
        parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, 128)
    ]
    inst = [
        parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS,
            actions
        ),
        parser.OFPInstructionGotoTable(1)
    ]
    mod = parser.OFPFlowMod(
        datapath=datapath,
        table_id=0,
        priority=0,
        match=match,
        instructions=inst
    )
    datapath.send_msg(mod)

    # Table 1: Forward packets based on learned MAC to port mapping
    match = parser.OFPMatch()
    actions = [
        parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, 128)
    ]
    inst = [
        parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS,
            actions
        )
    ]
    mod = parser.OFPFlowMod(
        datapath=datapath,
        table_id=1,
        priority=0,
        match=match,
        instructions=inst
    )
    datapath.send_msg(mod)

@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
def _packet_in_handler(self, ev):
    msg = ev.msg
    datapath = msg.datapath
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser
    in_port = msg.match['in_port']

    pkt = packet.Packet(msg.data)
    eth = pkt.get_protocol(ethernet.ethernet)

    assert eth is not None

    if eth.ethertype == ether_types.ETH_TYPE_LLDP:
        return

    src = eth.src
    dst = eth.dst

    # Learn MAC to port mapping
    self.mac_to_port[src] = in_port

    # Forwarding decision
    if dst in self.mac_to_port:
        out_port = self.mac_to_port[dst]
    else:
        # If destination MAC address is unknown, forward packet to neighbors
        neighbors = self.switch_neighbors[datapath.id]
        out_ports = [port for port in range(1, len(neighbors) + 1) if port != in_port]
        if out_ports:
            out_port = neighbors[out_ports.index(min(out_ports))]
        else:
            # If there are no valid output ports, drop the packet
            return

    actions = [parser.OFPActionOutput(out_port)]
    data = None
    if msg.buffer_id == ofproto.OFP_NO_BUFFER:
        data = msg.data
    out = parser.OFPPacketOut(
        datapath=datapath,
        buffer_id=msg.buffer_id,
        in_port=in_port,
        actions=actions,
        data=data
    )
    datapath.send_msg(out)
