import argparse
import utils

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-name', help='Environment name', type=str, required=True)
    parser.add_argument('-host', help='Database IP', type=str, required=True)
    parser.add_argument('-port', help='Database port', type=int, required=True)
    parser.add_argument('-user', help='Database user', type=str, required=True)
    args = vars(parser.parse_args())
    utils.exit_send_notification_to_influxdb(args.get("name"), args.get("host"), "database")
