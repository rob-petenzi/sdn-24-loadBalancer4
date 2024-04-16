from operator import attrgetter
from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub

class SimpleMonitor13(simple_switch_13.SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)

# Fills controller table with currently connected switches (dynamic)
@set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
def _state_change_handler(self, ev):
    datapath = ev.datapath  # Extract the datapath object from the event
    if ev.state == MAIN_DISPATCHER:
        # Handler for when the datapath (switch) transitions to MAIN_DISPATCHER state -> connected
        if datapath.id not in self.datapaths:
            # Check if the datapath is not already registered
            self.logger.debug('register datapath: %016x', datapath.id)
            self.datapaths[datapath.id] = datapath  # Register the datapath in a dictionary
    elif ev.state == DEAD_DISPATCHER:
        # Handler for when the datapath (switch) transitions to DEAD_DISPATCHER state -> disconnected
        if datapath.id in self.datapaths:
            # Check if the datapath is currently registered
            self.logger.debug('unregister datapath: %016x', datapath.id)
            del self.datapaths[datapath.id]  # Unregister and remove the datapath from the dictionary
    
    # Asks for stats for all switches each sleep_timer
    def _monitor(self):
        sleep_timer = 30;
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(sleep_timer)

    def _request_stats(self, datapath):
        # Log a debug message indicating that statistics requests are being sent to the specified datapath
        self.logger.debug('send stats request: %016x', datapath.id)

        # Obtain references to the OpenFlow protocol and parser objects associated with the datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Construct and send a flow statistics request to the datapath
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        # Construct and send a port statistics request to the datapath
        # Request statistics for all ports (port_no=0) using OFPP_ANY
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    # @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    # def _flow_stats_reply_handler(self, ev):
    #     body = ev.msg.body
    #     self.logger.info('datapath in-port eth-dst out-port packets bytes')
    #     self.logger.info('---------------- -------- ----------------- -------- -------- --------')
    #     for stat in sorted([flow for flow in body if flow.priority == 1],
    #                        key=lambda flow: (flow.match['in_port'], flow.match['eth_dst'])):
    #         self.logger.info('%016x %8x %17s %8x %8d %8d',
    #                          ev.msg.datapath.id,
    #                          stat.match['in_port'], stat.match['eth_dst'],
    #                          stat.instructions[0].actions[0].port,
    #                          stat.packet_count, stat.byte_count)

    # Handle replies for each switch
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        # Header for console output 
        self.logger.info('datapath port rx-pkts rx-bytes rx-error tx-pkts tx-bytes tx-error')
        self.logger.info('---------------- -------- -------- -------- -------- -------- -------- --------')
        # Sorts replies for each switch by port number, iterates through them and prints
        for stat in sorted(body, key=attrgetter('port_no')):
            self.logger.info('%016x %8x %8d %8d %8d %8d %8d %8d',
                             ev.msg.datapath.id, stat.port_no,
                             stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                             stat.tx_packets, stat.tx_bytes, stat.tx_errors)
        