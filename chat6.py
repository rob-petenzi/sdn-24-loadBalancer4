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
        self.port_load = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

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

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_FLOOD)
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
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        assert eth is not None

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src

        # Update port load
        self.port_load.setdefault(in_port, 0)
        self.port_load[in_port] += 1

        # Update MAC to port mapping
        self.mac_to_port[src] = in_port

        # Forwarding decision
        if src not in self.mac_to_port:
            # Add source address to table 0
            match = parser.OFPMatch(eth_src=src)
            inst = [
                parser.OFPInstructionGotoTable(1)
            ]
            mod = parser.OFPFlowMod(
                datapath=datapath,
                table_id=0,
                priority=1,
                match=match,
                instructions=inst
            )
            datapath.send_msg(mod)

        # Choose the least loaded path for forwarding
        least_loaded_port = min(self.port_load, key=self.port_load.get)
        out_port = least_loaded_port

        # Forward packet
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
