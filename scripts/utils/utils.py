import requests
from ..utils import configuration as cfg
import datetime as dt
import json


def send_notification_to_influxdb(env, host, status_code, agent_name):
    d = "agent_status,host=%s,agent=%s_agent status=%s" % (host, agent_name, status_code)
    send_data_to_influxdb(env, d, agent_name)


def send_notification_to_influxdb_with_error(env, host, error, status_code, agent_name):
    error = error.replace("\"", "'")
    d = "agent_status,host=%s,agent=%s_agent status=%s,error=\"%s\"" % (host, agent_name, status_code, error)
    send_data_to_influxdb(env, d, agent_name)


def send_data_to_influxdb(database, data, agent_name, precision=None):
    add_precition = ""
    auth_info = ""
    if precision is not None:
        add_precition = "&precision=" + precision
    if cfg.influxDb_user != "":
        auth_info = "u=%s&p=%s&" % (cfg.influxDb_user, cfg.influxDb_password)
    url = "http://%s/write?%sdb=%s%s" % (cfg.influxDb_host, auth_info, database, add_precition)
    r = requests.request('POST', url=url, data=data.encode('utf-8'))
    if r.status_code != 204:
        print(dt.datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S') + ' | ' + agent_name + ' | INFLUXDB ERROR | ' + database + ": " + r.text)


def get_data_from_influxdb(database, query):
    auth_info = ""
    if cfg.influxDb_user != "":
        auth_info = "u=%s&p=%s&" % (cfg.influxDb_user, cfg.influxDb_password)
    url = "http://%s/query?%sdb=%s&q=%s" % (cfg.influxDb_host, auth_info, database, query)
    r = requests.request('GET', url=url)
    result = ""
    if r.status_code != 200:
        print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | INFLUXDB ERROR | ' + database + ": " + r.text)
    else:
        result = json.loads(r.text)
    return result


def get_response_from_database(connection, sql):
    cur = connection.cursor('dict')
    cur.execute(sql)
    res = cur.fetchall()
    return res


def get_prepared_response_from_database(connection, sql, datetime):
    cur = connection.cursor('dict')
    cur.execute(sql, datetime)
    res = cur.fetchall()
    return res


def check_none_type(value):
    if value is None:
        return 0
    else:
        return value


def check_str_type(value):
    if isinstance(value, str):
        return "\"" + value + "\""
    else:
        return value


def exit_send_notification_to_influxdb(config, host, agent_name):
    print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' | AGENT | ' + agent_name + ": AGENT IS SHUTDOWN")
    send_notification_to_influxdb_with_error(config, host, "Agent is shutdown", cfg.status_code_error, agent_name)