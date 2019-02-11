import argparse
import os
from multiprocessing import Process
from ..utils import configuration as cfg
from pypsexec.client import Client
import datetime as dt
import time
from ..utils import utils
import atexit

network_command = 'Get-NetAdapterStatistics -Name "*" | Format-List -Property "*"'


def fetch_data_from_host_and_send_to_influxdb(config, client, host, counter):
    stdout, stderr, rc = client.run_executable("powershell", arguments=network_command)
    dataProc = stdout.decode()

    networkMeasurements = []
    dataProc = dataProc.split("\n\n")
    dataProc = list(filter(None, dataProc))
    for netApadterInfo in dataProc:
        if netApadterInfo == "\n":
            continue
        dctNetwork = {}
        currentNetInfo = netApadterInfo.replace("\r", "").split("\n")
        currentNetInfo = list(filter(None, currentNetInfo))
        measurements = ""
        for netAdapterInfoItem in currentNetInfo:
            if ":" not in netAdapterInfoItem:
                index = currentNetInfo.index(netAdapterInfoItem)
                currentNetInfo[index - 1:index + 1] = [
                    currentNetInfo[index - 1].rstrip() + " " + currentNetInfo[index].lstrip()]
        for netAdapterInfoItem in currentNetInfo:
            netApadterInfoItem = netAdapterInfoItem.split(":")
            key = netApadterInfoItem[0].replace(" ", "")
            value = netApadterInfoItem[1].strip()
            dctNetwork[key] = value
        for key in cfg.networkMetrics_windows:
            measurement_value = dctNetwork[key]
            if key == "Name":
                continue
            measurements = measurements + "{}={},".format(key, measurement_value)
        measurements = measurements[0:-1]
        d = "network,host=%s,interface=%s %s" % (host, dctNetwork.get("Name").replace(":", ""), measurements)
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
    client = Client("")
    while (state):
        try:
            counter = 0
            client = Client(host, username=user, port=port, password=password, encrypt=False)
            client.connect()
            client.create_service()
            try:
                while True:
                    counter = fetch_data_from_host_and_send_to_influxdb(config, client, host, counter)
                    counter += 1
                    time.sleep(cfg.call_interval)
            except Exception as e:
                print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | NETWORK | ERROR | ' + config + ' | ', e)
                utils.send_notification_to_influxdb_with_error(config, host, str(e), cfg.status_code_warning, "network")
        except Exception as e:
            if e == 'Authentication failed.':
                state = 0
                print(e)
            else:
                print(dt.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S') + ' | NETWORK | CONNECTION ERROR | ' + config + ' | ', e)
            utils.send_notification_to_influxdb_with_error(config, host, str(e), cfg.status_code_warning, "network")
        finally:
            client.remove_service()
            client.disconnect()
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