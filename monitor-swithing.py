from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event, switches
from ryu.topology.api import get_all_switch, get_all_link, get_all_host
from ryu.lib.packet import packet, ethernet, ether_types, arp, ipv4, tcp
from ryu.app import simple_switch_13
from ryu.lib import hub
from operator import attrgetter
import networkx as nx
import copy
from ryu.ofproto import inet, ether


class EnhancedHopByHopSwitch(simple_switch_13.SimpleSwitch13):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(EnhancedHopByHopSwitch, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.metrics = {}
        self.deltas = {}
        self.switches = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)])]
        mod = parser.OFPFlowMod(datapath=datapath, priority=0, match=parser.OFPMatch(), instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
                self._id_switch_translator()
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
                self._id_switch_translator()

    def _id_switch_translator(self):
        self.switches = {}
        ids = sorted(self.datapaths.keys())
        for i in range(0, ids.__len__):
            self.switches[ids[i]] = i
    
    def _monitor(self):
        sleep_timer = 10
        while True:
            hub.sleep(sleep_timer)
            for dp in self.datapaths.values():
                self._request_stats(dp)

    def _request_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)    

        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            self.proxy_arp(msg)
            return

        if eth.ethertype != ether_types.ETH_TYPE_IP:
            return

        destination_mac = eth.dst
        (dst_dpid, dst_port) = self.find_destination_switch(destination_mac)

        if dst_dpid is None:
            return

        if dst_dpid == datapath.id:
            output_port = dst_port
        else:
            output_port = self.find_next_hop_to_destination(datapath.id, dst_dpid)
        
        ip = pkt.get_protocol(ipv4.ipv4)
        
        if ip.proto == 1:
            match = parser.OFPMatch(eth_dst=destination_mac, eth_type=ether.ETH_TYPE_IP, ip_proto=inet.IPPROTO_ICMP)
            priority = 10
        elif ip.proto == 6:
            tcpinfo = pkt.get_protocol(tcp.tcp)
            if dst_dpid != datapath.id:
                print(f"\nMatching for {ip.src} {ip.dst} {tcpinfo.src_port} {tcpinfo.dst_port}")
                print(f"Datapath n{datapath.id} output on port n.{output_port} towards Datapath n.{dst_dpid}")
                self.periodic_print_deltas(datapath.id)
            priority = 20
            match = parser.OFPMatch(eth_dst=destination_mac, eth_type=ether.ETH_TYPE_IP, ip_proto=inet.IPPROTO_TCP, ipv4_src=str(ip.src), ipv4_dst=str(ip.dst), tcp_src=tcpinfo.src_port, tcp_dst=tcpinfo.dst_port)
            
        assert msg.buffer_id == ofproto.OFP_NO_BUFFER


        actions = [parser.OFPActionOutput(output_port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data)
        datapath.send_msg(out)

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [parser.OFPActionOutput(output_port)])]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst, buffer_id=msg.buffer_id)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        switch_id = ev.msg.datapath.id
        body = ev.msg.body
        port_traffic = {stat.port_no: stat.rx_bytes + stat.tx_bytes for stat in body}
        if switch_id in self.metrics:
            self.calculate_deltas(switch_id, port_traffic)
        self.metrics[switch_id] = port_traffic
        # self.periodic_print(switch_id)
        # self.periodic_print_deltas(switch_id)

    def calculate_deltas(self, switch, new_values):
        old_values = self.metrics.get(switch, {})
        switch_deltas = {port: new_values[port] - old_values.get(port, 0) for port in new_values}
        self.deltas[switch] = switch_deltas
        
           

    def periodic_print(self, switch):
        print("##########################")
        print("### Metric dict status for Switch {} ###".format(switch))
        print("##########################")
        for port, traffic in self.metrics[switch].items():
            print("Port {}: {}".format(port, traffic))
        print("\n")

    def periodic_print_deltas(self, switch):
        print("----------------------------------------")
        print("### Deltas dict status for Switch {} ###".format(switch))
        print("----------------------------------------")
        for port, delta in self.deltas[switch].items():
            if port < 10:
                print("Delta Port {}: {}".format(port, delta))
        # print("\n")

    def proxy_arp(self, msg):
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt_in = packet.Packet(msg.data)
        eth_in = pkt_in.get_protocol(ethernet.ethernet)
        arp_in = pkt_in.get_protocol(arp.arp)

        if arp_in.opcode != arp.ARP_REQUEST:
            return

        destination_host_mac = None
        for host in get_all_host(self):
            if arp_in.dst_ip in host.ipv4:
                destination_host_mac = host.mac
                break

        if destination_host_mac is None:
            return

        pkt_out = packet.Packet()
        eth_out = ethernet.ethernet(dst=eth_in.src, src=destination_host_mac, ethertype=ether_types.ETH_TYPE_ARP)
        arp_out = arp.arp(opcode=arp.ARP_REPLY, src_mac=destination_host_mac, src_ip=arp_in.dst_ip, dst_mac=arp_in.src_mac, dst_ip=arp_in.src_ip)
        pkt_out.add_protocol(eth_out)
        pkt_out.add_protocol(arp_out)
        pkt_out.serialize()

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER, in_port=ofproto.OFPP_CONTROLLER, actions=[parser.OFPActionOutput(in_port)], data=pkt_out.data)
        datapath.send_msg(out)

    def find_destination_switch(self, destination_mac):
        for host in get_all_host(self):
            if host.mac == destination_mac:
                return (host.port.dpid, host.port.port_no)
        return (None, None)

    def find_next_hop_to_destination(self, source_id, destination_id):
        net = nx.DiGraph()
        edge_weights =  {}
        # print("-----------------------------------------------------")
        # print("Switch SRC|     Switch DST    |    Weight   ")
        # print("-----------------------------------------------------")
        for link in get_all_link(self):
            net.add_edge(link.src.dpid, link.dst.dpid, port=link.src.port_no, weight=self.deltas[link.src.dpid].get(link.src.port_no))
            edge_weights[link.src.dpid, link.dst.dpid] = self.deltas[link.src.dpid].get(link.src.port_no)
            nx.set_edge_attributes(net, edge_weights, name='weight')
            # print(f"\t\t{link.src.dpid}\t\t\t\t{link.dst.dpid}      {self.deltas[link.src.dpid].get(link.src.port_no)}")
            
        path = nx.shortest_path(net, source_id, destination_id, weight='weight')
        for i in range(0, path.__len__):
            print(self.switches[path[i]] + " -> ")
        first_link = net[path[0]][path[1]]
        return first_link['port']