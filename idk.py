from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, icmp
import time

class PsrSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PsrSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.link_loads = {}
        self.monitor_interval = 10  # Monitoring interval in seconds
        self.last_monitor_time = time.time()
        self.visited_switches = {}  # Dictionary to store visited switches for each packet

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.mac_to_port[datapath.id] = {}

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]
        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=1,
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
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        assert eth is not None

        dst = eth.dst
        src = eth.src

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Handle ICMP packets separately
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt and ip_pkt.proto == ipv4.IPPROTO_ICMP:
                icmp_pkt = pkt.get_protocol(icmp.icmp)
                if icmp_pkt:
                    self.handle_icmp_packet(datapath, pkt, in_port)
                    return

        # Initialize visited switches list for this packet
        if src not in self.visited_switches:
            self.visited_switches[src] = []

        # Add current switch to visited switches list for this packet
        self.visited_switches[src].append(dpid)

        # Check if packet has visited this switch before
        if dpid in self.visited_switches[src]:
            # If packet has visited this switch before, drop the packet to avoid loops
            return

        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        assert msg.buffer_id == ofproto.OFP_NO_BUFFER

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        datapath.send_msg(out)

        if out_port != ofproto.OFPP_FLOOD:
            least_loaded_port = self.get_least_loaded_port(datapath)
            match = parser.OFPMatch(
                eth_src=src,
                eth_dst=dst
            )
            actions = [
                parser.OFPActionOutput(least_loaded_port)
            ]
            inst = [
                parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS,
                    actions
                )
            ]
            ofmsg = parser.OFPFlowMod(
                datapath=datapath,
                priority=10,
                match=match,
                instructions=inst,
            )
            datapath.send_msg(ofmsg)

    def handle_icmp_packet(self, datapath, pkt, in_port):
        # Flood ICMP packets
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=pkt.data
        )
        datapath.send_msg(out)

    def get_least_loaded_port(self, datapath):
        # Check if it's time to update link loads
        current_time = time.time()
        if current_time - self.last_monitor_time >= self.monitor_interval:
            self.update_link_loads(datapath)
            self.last_monitor_time = current_time

        # Find the least loaded port
        least_loaded_port = min(self.link_loads[datapath.id], key=self.link_loads[datapath.id].get)
        return least_loaded_port

    def update_link_loads(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        ports = self.get_switch_ports(datapath)

        # Query port statistics for each port
        for port in ports:
            port_stats = self.get_port_stats(datapath, port)
            self.link_loads[datapath.id][port] = port_stats['tx_packets']

    def get_switch_ports(self, datapath):
        ports = []
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        port_stats_request = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        port_stats_reply = datapath.send_msg(port_stats_request)
        for stat in port_stats_reply:
            ports.append(stat.port_no)
        return ports

    def get_port_stats(self, datapath, port):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        port_stats_request = parser.OFPPortStatsRequest(datapath, 0, port)
        port_stats_reply = datapath.send_msg(port_stats_request)
        for stat in port_stats_reply:
            return stat
