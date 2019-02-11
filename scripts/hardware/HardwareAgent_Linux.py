import argparse
import os
from multiprocessing import Process
from ..utils import configuration as cfg
import paramiko
import datetime as dt
import time
import atexit
from ..utils import utils

process_info_command = "top -bn1 -p $(/usr/sbin/pidof vertica | sed 's/ /, /g')"
cpu_command = "mpstat -P ALL 1 2"
hdd_command = "df"
hdd_detailed_command = "iostat -xtc 1 2"
ram_command = "vmstat 1 2"


def fetch_data_from_host_and_send_to_influxdb(config, client, host, counter):
    # Process info
    processMeasurements = []
    stdin, stdout, stderr = client.exec_command(process_info_command)
    dataProc = stdout.read() + stderr.read()
    dataProc = dataProc.decode().split("\n\n")[-1].split("\n")
    keysProc = dataProc[0].split()
    dataProc = dataProc[1:len(dataProc) - 1]
    for i in dataProc:
        valuesProc = i.split()
        dctCPU = dict(zip(keysProc, valuesProc))
        measurements = ""
        for key in cfg.processMetrics_linux:
            measurement_value = dctCPU[key]
            if key == "VIRT" or key == "RES" or key == "SHR":
                if measurement_value.endswith("g"):
                    measurement_value = float(measurement_value[:-1]) * 1000000
                elif measurement_value.endswith("m"):
                    measurement_value = float(measurement_value[:-1]) * 1000
            if key == "USER" or key == "S" or key == "TIME+" or key == "COMMAND" or key == "PR":
                measurement_value = "\"" + measurement_value + "\""
            measurements = measurements + "{}={},".format(key.replace("%", ""), measurement_value)
        measurements = measurements[0:-1]  # strip the last comma
        d = "process,host=%s %s" % (host, measurements)
        processMeasurements.append(d)

    result_str = "\n".join(processMeasurements)
    utils.send_data_to_influxdb(config, result_str, "hardware")

    # CPU usage
    # mpstat -P ALL 1 2
    cpuMeasurements = []

    stdinCPU, stdoutCPU, stderrCPU = client.exec_command(cpu_command)
    dataCPU = stdoutCPU.read() + stderrCPU.read()
    dataCPU = dataCPU.decode().split("\n\n")[-2].split("\n")
    keysCPU = dataCPU[0].split()
    keysCPU = keysCPU[2:len(keysCPU)]
    dataCPU = dataCPU[2:len(dataCPU)]

    for i in dataCPU:
        valuesCPU = i.split()
        valuesCPU = valuesCPU[2:len(i)]
        dctCPU = dict(zip(keysCPU, valuesCPU))
        measurements = ""
        for key in cfg.cpuMetrics_linux:
            measurement_value = dctCPU[key]
            measurements = measurements + "{}={},".format(key.replace("/", "_").replace("%", ""), measurement_value)
        measurements = measurements[0:-1]
        d = "cpu,host=%s,core=%s %s" % (host, "core_" + str(dctCPU.get("CPU")), measurements)
        cpuMeasurements.append(d)

    result_str = "\n".join(cpuMeasurements)
    utils.send_data_to_influxdb(config, result_str, "hardware")

    # HDD usage
    # df
    dataMeasurements = {}

    stdinIO, stdoutIO, stderrIO = client.exec_command(hdd_command)
    dataIO = stdoutIO.read() + stderrIO.read()
    dataIO = dataIO.decode().split("\n")
    keysIO = dataIO[0].split()
    keysIO[5:7] = ['_'.join(map(str, keysIO[5:7]))]
    dataIO = dataIO[1:len(dataIO) - 1]
    for i in dataIO:
        valuesIO = i.split()
        dctIO = dict(zip(keysIO, valuesIO))
        filesystem = dctIO.get('Filesystem')
        if filesystem.startswith('/dev/'):
            filesystem = filesystem.replace("/dev/", "")
            if filesystem.startswith('sda'):
                filesystem = "sda"
            dctIO['Filesystem'] = filesystem
            measurements = "used=%s,available=%s" % (dctIO.get('Used'), dctIO.get('Available'))
            dataMeasurements[filesystem] = measurements

    # iostat -xtc 1 2

    dataIOMeasurements = []

    stdinIO, stdoutIO, stderrIO = client.exec_command(hdd_detailed_command)
    dataIO = stdoutIO.read() + stderrIO.read()
    dataIO = dataIO.decode().split("\n\n")[-2].split("\n")
    keysIO = dataIO[0].split()
    dataIO = dataIO[1:len(dataIO)]
    for i in dataIO:
        valuesIO = i.split()
        dctIO = dict(zip(keysIO, valuesIO))
        measurements = ""
        for key in cfg.hddMetrics_linux:
            measurement_value = dctIO[key]
            measurements = measurements + "{}={},".format(key.replace("/", "_"), measurement_value)
        measurements = measurements + dataMeasurements.get(dctIO.get("Device:"))  # strip the last comma
        d = "hdd,host=%s,disk=%s %s" % (host, dctIO.get("Device:"), measurements)
        dataIOMeasurements.append(d)
    result_str = "\n".join(dataIOMeasurements)
    utils.send_data_to_influxdb(config, result_str, "hardware")

    # RAM usage
    # vmstat 1 2
    otherMeasurements = []

    stdin, stdout, stderr = client.exec_command(ram_command)
    data = stdout.read() + stderr.read()
    data = data.decode().split("\n")

    keys = data[1].split()
    values = data[-2].split()
    dct = dict(zip(keys, values))

    measurements = ""
    for key in cfg.ramMetrics_linux:
        measurement_value = dct[key]
        measurements = measurements + "{}={},".format(key, measurement_value)
    measurements = measurements[0:-1]

    ram_data = "ram,host=%s %s" % (host, measurements)
    otherMeasurements.append(ram_data)
    result_str = "\n".join(otherMeasurements)
    utils.send_data_to_influxdb(config, result_str, "hardware")

    if counter == 10:
        utils.send_notification_to_influxdb(config, host, cfg.status_code_ok, "hardware")
        counter = 0
    return counter


def run(arguments=None, state=1):
    config = arguments.get("name")
    host = arguments.get("host")
    port = arguments.get("port")
    user = arguments.get("user")
    password = os.environ.get('PFTOOL_USER_PASSWORD')
    print("[HARDWARE] Started agent for '" + config + "' [" + str(host) + "]")
    print("[HARDWARE] Agent args: name='%s' host='%s' port='%s' user='%s' password='%s'" % (
        config, host, port, user, password))
    utils.send_notification_to_influxdb(config, host, cfg.status_code_ok, "hardware")
    client = paramiko.SSHClient()
    while (state):
        try:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, username=user, password=password, port=port)
            counter = 0
            try:
                while True:
                    time.sleep(cfg.call_interval)
                    counter = fetch_data_from_host_and_send_to_influxdb(config, client, host, counter)
                    counter += 1
            except Exception as e:
                print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | HARDWARE | ERROR | ' + config + ' | ', e)
                utils.send_notification_to_influxdb_with_error(config, host, "[Retrieving data error]" + str(e),
                                                               cfg.status_code_warning, "hardware")
        except Exception as e:
            if e == 'Authentication failed.':
                state = 0
                print(e)
            else:
                print(dt.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S') + ' | HARDWARE | CONNECTION ERROR | ' + config + ' | ', e)
            utils.send_notification_to_influxdb_with_error(config, host, "[Connection to host error]" + str(e),
                                                           cfg.status_code_warning, "hardware")
        finally:
            client.close()
    utils.send_notification_to_influxdb_with_error(config, host, "Work finished", cfg.status_code_error, "hardware")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-name', help='Environment name', type=str, required=True)
    parser.add_argument('-host', help='Host IP', type=str, required=True)
    parser.add_argument('-port', help='Host port', type=int, required=True)
    parser.add_argument('-user', help='Host user', type=str, required=True)
    args = vars(parser.parse_args())
    agent_process = Process(target=run, args=(args,))
    agent_process.start()
    agent_process.join()
    atexit.register(utils.exit_send_notification_to_influxdb, args.get("name"), args.get("host"), "hardware")
