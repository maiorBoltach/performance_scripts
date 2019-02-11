import atexit
import argparse
import os
import time
from datetime import datetime, timedelta
from multiprocessing import Process
from pytz import timezone
from ..utils import configuration as cfg
import vertica_python
from ..utils import utils

node_status_sql = "SELECT /*+LABEL(PERFORMANCE_AGENT)*/ node_name, node_state FROM nodes"
request_history = "SELECT /*+LABEL(PERFORMANCE_AGENT)*/ node_name, user_name, request_id, transaction_id, statement_id, request_type, request, request_label, memory_acquired_mb,success, error_count, start_timestamp, end_timestamp, request_duration_ms, is_executing FROM v_monitor.query_requests WHERE statement_id > 0 AND transaction_id > 0 AND (start_timestamp > :param OR end_timestamp > :param OR is_executing='t')"
request_history_fix = "SELECT /*+LABEL(PERFORMANCE_AGENT)*/ node_name, user_name, request_id, transaction_id, statement_id, request_type, request, request_label, memory_acquired_mb,success, error_count, start_timestamp, end_timestamp, request_duration_ms, is_executing FROM v_monitor.query_requests WHERE (transaction_id, request_id) IN (%s)"
request_distribution = "SELECT /*+LABEL(PERFORMANCE_AGENT)*/ node_name, argument_value.requests, ROUND((argument_value.requests / b.total_requests) * 100, 2.0) AS percent FROM (SELECT node_name, COUNT(*) AS requests FROM v_monitor.query_requests GROUP  BY node_name) argument_value CROSS JOIN (SELECT COUNT(*) AS total_requests FROM v_monitor.query_requests) b"
database_systime = "SELECT /*+LABEL(PERFORMANCE_AGENT)*/ sysdate"


def parse_query_history(host, res):
    request_history_result = []
    for f in res:
        node_name = str(f.get("node_name"))
        transaction_id = str(f.get("transaction_id"))
        request_type = str(f.get("request_type"))
        request_label = str(f.get("request_label"))
        request_id = str(f.get("request_id"))

        user_name = utils.check_str_type(f.get("user_name"))
        statement_id = f.get("statement_id")
        request = utils.check_str_type(f.get("request").replace("\"", "\\\""))
        memory_acquired_mb = utils.check_none_type(f.get("memory_acquired_mb"))
        success = f.get("success")
        error_count = utils.check_none_type(f.get("error_count"))
        request_duration_ms = utils.check_none_type(f.get("request_duration_ms"))
        is_executing = f.get("is_executing")

        if request_label == '':
            request_label = 'OTHER'

        start_timestamp = f.get("start_timestamp")
        end_timestamp = f.get("end_timestamp")

        measurement = "user_name=%s,statement_id=%s,request=%s,memory_acquired_mb=%s,success=%s,error_count=%s," \
                      "request_duration_ms=%s,is_executing=%s" % \
                      (user_name, statement_id, request, memory_acquired_mb, success, error_count, request_duration_ms,
                       is_executing)

        query = "database_history,host=%s,node_name=%s,transaction_id=%s,request_id=%s,request_label=%s,request_type=%s %s" % \
                (host, node_name, transaction_id, request_id, request_label, request_type, measurement)

        start_query = "%s%s %s" % (
            query, ",point_type=\"start\",point_value=1",
            int(start_timestamp.astimezone(timezone('UTC')).timestamp() * 1000))
        start_query = start_query.replace(",success=None", "")

        end_query = ""

        if end_timestamp is not None:
            end_query = "%s%s %s" % (
                query, ",point_type=\"end\",point_value=0",
                int(end_timestamp.astimezone(timezone('UTC')).timestamp() * 1000))
        else:
            end_query = "%s%s" % (query, ",point_type=\"intermediate\",point_value=1")
            end_query = end_query.replace(",success=None", "").replace(",is_executing=True", "")
        request_history_result.append(start_query)
        request_history_result.append(end_query)

    result_str = "\n".join(request_history_result)
    return result_str


def fetch_data_from_host_and_send_to_influxdb(config, connection, host, counter, curr_time):
    # Get nodes status
    nodes_status = []
    res = utils.get_response_from_database(connection, node_status_sql)
    for f in res:
        node_name = f.get("node_name")
        node_status = f.get("node_state")
        d = "database,host=%s,node_name=%s node_state=\"%s\"" % (host, node_name, node_status)
        nodes_status.append(d)

    result_str = "\n".join(nodes_status)
    utils.send_data_to_influxdb(config, result_str, "database")

    # Get query history
    res = utils.get_prepared_response_from_database(connection, request_history,
                                                    {'param': curr_time.strftime("%Y-%m-%d %H:%M:%S")})
    result_str = parse_query_history(host, res)
    utils.send_data_to_influxdb(config, result_str, "database", "ms")

    ## Shows cluster request distribution to identify potential load balancing issues
    ## http://j.mp/vertica-request-distribution

    res = utils.get_response_from_database(connection, request_distribution)
    request_distribution_array = []
    for f in res:
        node_name = str(f.get("node_name"))
        requests_count = str(f.get("requests"))
        percent = str(f.get("percent"))
        d = "database,host=%s,node_name=%s requests_count=%s,percent=%s" % (host, node_name, requests_count, percent)
        request_distribution_array.append(d)

    result_str = "\n".join(request_distribution_array)
    utils.send_data_to_influxdb(config, result_str, "database")

    if counter == 10:
        utils.send_notification_to_influxdb(config, host, cfg.status_code_ok, "database")
        counter = 0
    return counter


def fix_query_history(config, connection, host):
    influxdb_request = "select transaction_id,statement_id from database_history WHERE is_executing=true"
    influxdb_results = utils.get_data_from_influxdb(config, influxdb_request)['results'][0]['series'][0]['values']
    transactions = set()
    for transaction in influxdb_results:
        transactions.add("(" + str(transaction[1]) + "," + str(transaction[2]) + ")")
    result_str = ",".join(transactions)
    request_history = request_history_fix % result_str
    res = utils.get_response_from_database(connection, request_history)
    result_str = parse_query_history(host, res)
    utils.send_data_to_influxdb(config, result_str, "database", "ms")


def get_database_timedelta(connection):
    res = utils.get_response_from_database(connection, database_systime)
    database_time = res[0].get("sysdate")
    return database_time


def run(arguments=None, state=1):
    config = arguments.get("name")
    host = arguments.get("host")
    port = arguments.get("port")
    user = arguments.get("user")
    password = os.environ.get('PFTOOL_DB_PASSWORD')
    print("[DATABASE] Agent args: name='%s' host='%s' port='%s' user='%s' password='%s'" % (
        config, host, port, user, password))
    print("[DATABASE] Started agent for '" + config + "'")
    utils.send_notification_to_influxdb(config, host, cfg.status_code_ok, "database")
    connection = None
    while (state):
        try:
            conn_info = {'host': host,
                         'port': port,
                         'user': user,
                         'password': password,
                         'read_timeout': 600,
                         'unicode_error': 'replace'}
            connection = vertica_python.connect(**conn_info)
            counter = 0
            try:
                database_time = get_database_timedelta(connection)
                monitoring_time = datetime.now()
                timeDeltaSeconds = (monitoring_time - database_time).total_seconds()
                timedeltaTZ = int(divmod(timeDeltaSeconds, 3600)[0])
                print(timedeltaTZ)
                curr_time = database_time - timedelta(seconds=cfg.database_call_interval * 2)
                while True:
                    counter = fetch_data_from_host_and_send_to_influxdb(config, connection, host, counter, curr_time)
                    curr_time = datetime.now() - timedelta(seconds=2 * cfg.database_call_interval) + timedelta(
                        hours=timedeltaTZ)
                    counter += 1
                    time.sleep(cfg.database_call_interval)
                    if counter % 5 == 0:
                        fix_query_history(config, connection, host)
            except Exception as e:
                print(datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | ERROR | ' + config + ' | ', e)
                utils.send_notification_to_influxdb_with_error(config, host, "[Query request error]" + str(e),
                                                               cfg.status_code_warning, "database")
        except Exception as e:
            if e == 'Authentication failed.':
                state = 0
                print(e)
            else:
                print(datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | CONNECTION ERROR | ' + config + ' | ', e)
            utils.send_notification_to_influxdb_with_error(config, host, "[Connection to DB error]" + str(e),
                                                           cfg.status_code_warning, "database")
        finally:
            if connection is not None:
                connection.close()
    utils.send_notification_to_influxdb_with_error(config, host, "Work finished", cfg.status_code_error, "database")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-name', help='Environment name', type=str, required=True)
    parser.add_argument('-host', help='Database IP', type=str, required=True)
    parser.add_argument('-port', help='Database port', type=int, required=True)
    parser.add_argument('-user', help='Database user', type=str, required=True)
    args = vars(parser.parse_args())
    agent_process = Process(target=run, args=(args,))
    agent_process.start()
    agent_process.join()
    atexit.register(utils.exit_send_notification_to_influxdb, args.get("name"), args.get("host"), "database")
