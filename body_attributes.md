# Extracting data from Reply
Use `operator.attrgetter`: `data = sorted(body, key=arrtgetter('field'))`, where field is one of the listed below.
## Attributes commonly found in OFPPortStats objects retrieved from ev.msg.body:
- port_no: Port number (e.g., 1, 2, 3, ...)
- rx_packets: Number of received packets on the port
- tx_packets: Number of transmitted packets from the port
- rx_bytes: Number of received bytes on the port
- tx_bytes: Number of transmitted bytes from the port
- rx_errors: Number of receive errors on the port
- tx_errors: Number of transmit errors from the port
- rx_dropped: Number of received packets dropped by the port
- tx_dropped: Number of transmitted packets dropped by the port
- duration_sec: Time in seconds during which these statistics have been collected
- duration_nsec: Additional nanoseconds beyond duration_sec
OFPFlowStats (Flow Statistics):

## Attributes commonly found in OFPFlowStats objects retrieved from ev.msg.body:
- table_id: ID of the flow table
- duration_sec: Time in seconds during which the flow statistics - have been collected
- duration_nsec: Additional nanoseconds beyond duration_sec
priority: Priority level of the flow entry
- cookie: Opaque cookie value associated with the flow entry
- packet_count: Number of packets matched by the flow entry
- byte_count: Number of bytes matched by the flow entry
- match: Match fields (e.g., in_port, eth_src, eth_dst, etc.) defining the flow's match criteria