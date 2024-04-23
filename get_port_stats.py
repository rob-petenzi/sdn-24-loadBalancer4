from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
import json
import time
from operator import attrgetter
import copy

class SimpleMonitor13(simple_switch_13.SimpleSwitch13):
  metrics = {}
  deltas = {}
  def __init__(self, *args, **kwargs):
    super(SimpleMonitor13, self).__init__(*args, **kwargs)
    self.datapaths = {}
    self.monitor_thread = hub.spawn(self._monitor)
    self.metrics = {}
    self.deltas = {}

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
    sleep_timer = 30
    while True:
      hub.sleep(sleep_timer)
      for dp in self.datapaths.values():
        self._request_stats(dp)
      self.periodic_print()
      self.periodic_print_deltas()


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

  # Handle replies for each switch
  @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
  def _port_stats_reply_handler(self, ev):
    switch_id = ev.msg.datapath.id
    port_traffic = {}
    # Sorts replies for each switch by port number, iterates through them and prints
    self.logger.debug("---------------------------")
    self.logger.debug("Switch: %03x", switch_id)
    for stat in sorted(ev.msg.body, key=attrgetter("port_no")):
      total_traffic = stat.rx_bytes + stat.tx_bytes
      port_traffic[stat.port_no] = total_traffic
      # TODO if to discard giant port
    for key in port_traffic.keys():
      self.logger.debug("%8d: %8d", key, port_traffic.get(key))
    self.logger.debug("---------------------------")
    if(port_traffic != {}):
      if(switch_id in self.metrics.keys()):
        self.calculate_deltas(switch=switch_id, new_values=port_traffic)
      if switch_id not in self.metrics.keys():
        self.metrics[switch_id] = port_traffic
      else:
        self.metrics[switch_id].update(port_traffic)

  def periodic_print(self):
    print("##########################")
    print("### Metric dict status ###")
    print("##########################")
    for switch, port_traffic in self.metrics.items():
      port1 = port_traffic[1]
      port2 = port_traffic[2]
      self.logger.info(f"Switch {switch}: port1 = {port1}, port2 = {port2}")
      self.logger.info("-------------------")
    print("\n")
      
  def periodic_print_deltas(self):
    print("##########################")
    print("### Deltas dict status ###")
    print("##########################")
    for switch, port_traffic in self.deltas.items():
      port1 = port_traffic[1]
      port2 = port_traffic[2]
      self.logger.info(f"Switch {switch}: delta_port1 = {port1}, delta_port2 = {port2}")
      self.logger.info("-------------------")
      
  def calculate_deltas(self, switch, new_values):
    old_values = self.metrics.get(switch)
    # Casually fill switch_deltas with one of metric's value to avoid null
    switch_deltas = copy.deepcopy(self.metrics[switch])
    for port in new_values.keys():
      switch_deltas[port] = new_values[port] - old_values[port]
    if switch not in self.deltas.keys():
      self.deltas[switch] = switch_deltas
    else:
      self.deltas[switch].update(switch_deltas)