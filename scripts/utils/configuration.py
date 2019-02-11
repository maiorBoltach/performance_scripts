#
# influxDb configs
#

influxDb_host = "localhost:8086"
influxDb_user = ""
influxDb_password = ""

#
# monitoring host settings
#

linux_host_mapping = {"dev": [{'host': "10.148.0.4", 'port': 22, 'user': "admin", 'password': "password"}],
                        "qa": [{'host': "10.148.0.3", 'port': 22, 'user': "admin", 'password': "TP8B9JDX"}]
                      }

windows_host_mapping = {"microstrategy": [{'host': "192.168.0.103", 'port': 445, 'user': "admin", 'password': "password"}]}

database_mapping = {"dev": {'host': "10.148.0.4", 'port': 5433, 'user': "dbadmin", 'password': "password"},
                    "qa": {'host': "10.148.0.3", 'port': 5433, 'user': "dbadmin", 'password': "password"}}


#
# monitoring settings
#

status_code_ok = 100
status_code_warning = 50
status_code_error = 0
call_interval = 10
database_call_interval = 20

# network net/dev
networkMetrics_linux = ['receive_bytes', 'receive_packets', 'receive_errs', 'receive_drop', 'receive_fifo',
                        'receive_frame', 'receive_compressed', 'receive_multicast',
                        'transmit_bytes', 'transmit_packets', 'transmit_errs', 'transmit_drop', 'transmit_fifo',
                        'transmit_colls', 'transmit_carrier', 'transmit_compressed']


networkMetrics_windows = ['ReceivedBroadcastBytes', 'ReceivedBroadcastPackets', 'ReceivedBytes', 'ReceivedDiscardedPackets',
                          'ReceivedMulticastBytes', 'ReceivedMulticastPackets', 'ReceivedPacketErrors', 'ReceivedUnicastBytes',
                          'ReceivedUnicastPackets',
                          'SentBroadcastBytes', 'SentBroadcastPackets', 'SentBytes', 'SentMulticastBytes',
                          'SentMulticastPackets', 'SentUnicastBytes', 'SentUnicastPackets', 'OutboundDiscardedPackets',
                          'OutboundPacketErrors']

# cpu stats
cpuMetrics_linux = ["%usr", "%nice", "%sys", "%iowait", "%irq", "%soft", "%steal", "%guest", "%gnice", "%idle"]

# hdd stats
hddMetrics_linux = ["rrqm/s", "wrqm/s", "rkB/s", "wkB/s", "avgrq-sz", "avgqu-sz", "r/s", "w/s",
                    "await", "r_await", "w_await", "svctm", "%util"]

# process stats
processMetrics_linux = ["PID", "USER", "PR", "NI", "VIRT", "RES", "SHR", "S", "%CPU", "%MEM", "TIME+", "COMMAND"]

# ram stats
ramMetrics_linux = ["swpd", "free", "buff", "cache"]