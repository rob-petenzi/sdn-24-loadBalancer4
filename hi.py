from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link

class SDNController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SDNController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.graph = {}

    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        switch_list = get_switch(self, None)
        switches = [switch.dp.id for switch in switch_list]
        self.graph = {dpid: {} for dpid in switches}

        link_list = get_link(self, None)
        for link in link_list:
            src = link.src.dpid
            dst = link.dst.dpid
            self.graph[src][dst] = link
            self.graph[dst][src] = link

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()

        # Send all packets to the controller
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    def find_least_loaded_link(self, src_dpid):
        min_load = float('inf')
        least_loaded_link = None
        for dst_dpid, link in self.graph[src_dpid].items():
            if link and link.src.dpid == src_dpid:
                load = link.src.port_no
                if load < min_load:
                    min_load = load
                    least_loaded_link = link
        return least_loaded_link

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # Parse the packet
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)

        # Check if it's ARP
        if eth_pkt.ethertype == ether_types.ETH_TYPE_ARP:
            # Handle ARP packets
            # You can implement ARP handling logic here
            pass

        # Check if it's IPv4
        elif eth_pkt.ethertype == ether_types.ETH_TYPE_IP:
            # Handle IPv4 packets
            # You can implement IPv4 handling logic here
            pass

        # Add logic for other packet types as needed

        # Install flow rule to forward subsequent packets
        dst_mac = eth_pkt.dst
        src_mac = eth_pkt.src
        dpid = datapath.id
        out_port = self.mac_to_port[dpid].get(dst_mac)

        if out_port is None:
            # Flood the packet
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac, eth_src=src_mac)
        self.add_flow(datapath, 1, match, actions)
        self.logger.info("Installed flow rule on switch %s: match %s, actions %s", dpid, match, actions)

    @set_ev_cls(event.EventSwitchLeave)
    def _event_switch_leave_handler(self, ev):
        datapath_id = ev.switch.dp.id
        if datapath_id in self.mac_to_port:
            del self.mac_to_port[datapath_id]

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        msg = ev.msg
        reason = msg.reason
        ofp = msg.datapath.ofproto
        ofp_parser = msg.datapath.ofproto_parser
        port_no = msg.desc.port_no
        hw_addr = msg.desc.hw_addr
        dpid = msg.datapath.id

        if reason == ofp.OFPPR_ADD:
            self.logger.info("Port added %s", port_no)
        elif reason == ofp.OFPPR_DELETE:
            self.logger.info("Port deleted %s", port_no)
        elif reason == ofp.OFPPR_MODIFY:
            self.logger.info("Port modified %s", port_no)
        else:
            self.logger.info("Illegal port state %s %s", port_no, reason)

        # Update mac_to_port mapping
        if hw_addr != "00:00:00:00:00:00" and reason == ofp.OFPPR_ADD:
            self.mac_to_port.setdefault(dpid, {})
            self.mac_to_port[dpid][hw_addr] = port_no
