import argparse
import atexit
import os
from multiprocessing import Process
import configuration as cfg
import paramiko
import time
import utils
import datetime as dt

network_command = "cat /proc/net/dev"


def fetch_data_from_host_and_send_to_influxdb(config, client, host, counter):
    networkMeasurements = []
    stdin, stdout, stderr = client.exec_command(network_command)
    dataProc = stdout.read() + stderr.read()
    dataProc = dataProc.decode().split("\n")
    dataFirstHeader = dataProc[0].split("|")
    dataSecondHeader = dataProc[1].split("|")
    dataString = dataProc[2:-1]

    dataHeader = ["interface"]
    for columnsName in dataSecondHeader[1:]:
        colNumber = dataSecondHeader.index(columnsName)
        columnsName = columnsName.split()
        for columnName in columnsName:
            dataHeader.append(dataFirstHeader[colNumber].lower().strip() + "_" + columnName)

    for interfaceData in dataString:
        interfaceData = interfaceData.split()
        dctNetwork = dict(zip(dataHeader, interfaceData))
        measurements = ""
        for key in cfg.networkMetrics_linux:
            measurement_value = dctNetwork[key]
            if key == "interface":
                continue
            measurements = measurements + "{}={},".format(key, measurement_value)
        measurements = measurements[0:-1]  # strip the last comma
        d = "network,host=%s,interface=%s %s" % (host, dctNetwork.get("interface").replace(":", ""), measurements)
        networkMeasurements.append(d)

    result_str = "\n".join(networkMeasurements)
    utils.send_data_to_influxdb(config, result_str, "network")
    if counter == 10:
        utils.send_notification_to_influxdb(config, host, cfg.status_code_ok, "network")
        counter = 0
    return counter


def run(arguments=None, state=1):
    config = arguments.get("name")
    host = arguments.get("host")
    port = arguments.get("port")
    user = arguments.get("user")
    password = os.environ.get('PFTOOL_USER_PASSWORD')
    print("[NETWORK] Started agent for '" + config + "' [" + str(host) + "]")
    print("[NETWORK] Agent args: name='%s' host='%s' port='%s' user='%s' password='%s'" % (
        config, host, port, user, password))
    utils.send_notification_to_influxdb(config, host, cfg.status_code_ok, "network")
    client = paramiko.SSHClient()
    while (state):
        try:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, username=user, password=password, port=port)
            counter = 0
            try:
                while True:
                    counter = fetch_data_from_host_and_send_to_influxdb(config, client, host, counter)
                    counter += 1
                    time.sleep(cfg.call_interval)

            except Exception as e:
                print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | NETWORK | ERROR | ' + config + ' | ', e)
                utils.send_notification_to_influxdb_with_error(config, host, "[Retrieving data error]" + str(e),
                                                               cfg.status_code_warning, "network")

        except Exception as e:
            if e == 'Authentication failed.':
                state = 0
                print(e)
            else:
                print(dt.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S') + ' | NETWORK | CONNECTION ERROR | ' + config + ' | ', e)
            utils.send_notification_to_influxdb_with_error(config, host, "[Connection to host error]" + str(e),
                                                           cfg.status_code_warning, "network")

        finally:
            client.close()
    utils.send_notification_to_influxdb_with_error(config, host, "Work finished", cfg.status_code_error, "network")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-name', help='Environment name', type=str, required=True)
    parser.add_argument('-host', help='Host IP', type=str, required=True)
    parser.add_argument('-port', help='Host port', type=int, required=True)
    parser.add_argument('-user', help='Host user', type=str, required=True)
    args = vars(parser.parse_args())
    agent_process = Process(target=run, args=(args, ))
    agent_process.start()
    agent_process.join()
    atexit.register(utils.exit_send_notification_to_influxdb, args.get("name"), args.get("host"), "network")