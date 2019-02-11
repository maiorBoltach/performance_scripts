#!/bin/bash
echo "Installing new host services..."
echo "DB Name: $1"
echo "Host IP: $2"
echo "Host port: $3"
echo "Host user: $4"
WORKING_DIR=$(dirname $(readlink -f $0))
REPLACE_STR="s@{{ virtualenv_dir }}@$VIRTUALENV_PATH@g; \
    s@{{ agent_scripts_dir }}@$WORKING_DIR@g; \
    s@{{ item.value.dbname }}@$1@g; \
    s@{{ item.value.ip }}@$2@g; \
    s@{{ agent_ssh_port }}@$3@g; \
    s@{{ agent_ssh_user }}@$4@g"
HARDWARE_SERVICE_NAME=hardware_$2
NETWORK_SERVICE_NAME=network_$2
sed "$REPLACE_STR" $WORKING_DIR/services/hardware/hardware_linux_agent.service > /etc/systemd/system/$HARDWARE_SERVICE_NAME.service
sed "$REPLACE_STR" $WORKING_DIR/services/hardware/network_linux_agent.service > /etc/systemd/system/$NETWORK_SERVICE_NAME.service
systemctl daemon-reload
systemctl enable $HARDWARE_SERVICE_NAME
systemctl enable $NETWORK_SERVICE_NAME
systemctl start $HARDWARE_SERVICE_NAME
systemctl start $NETWORK_SERVICE_NAME
