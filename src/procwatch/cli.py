#!/usr/bin/env python3

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
import time
from typing import Any, List, Optional

import psutil

# ----------------------------
# Presets (Variables)
# ----------------------------

PID = "pid"
NAME = "name"
USERNAME = "username"
STATUS = "status"
CMDLINE = "cmdline"
PROCESS_FIELDS = [PID, NAME, USERNAME, STATUS, CMDLINE]
assert all(f in psutil.Process().as_dict().keys() for f in PROCESS_FIELDS)
CONNECTIONS = "connections"


NO_MATCH_FOUND = "No matching process found."


# ----------------------------
# Logging
# ----------------------------


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


def log_config(logfile: str | None = None, json_out: bool = False):
    formatter = (
        JsonFormatter()
        if json_out
        else logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
    )
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # stdout handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # file handler

    if logfile:
        try:
            file_handler = logging.FileHandler(logfile)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (PermissionError, FileNotFoundError) as e:
            logger.error(f"Log File Error: {e}")

    return logger


# ----------------------------
# CLI
# ----------------------------


def valid_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def valid_pid(value: str) -> int:
    pid = int(value)
    if pid <= 0:
        raise argparse.ArgumentTypeError("PID must be > 0")
    return pid


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process watchdog")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pid", type=valid_pid, help="Monitor specific PID, (PID > 0)")
    group.add_argument(
        "--port", type=valid_port, help="Monitor service by port, (1 <= port <= 65535)"
    )
    group.add_argument(
        "--name", type=str.lower, help="Monitor process by name, (substring match)"
    )

    parser.add_argument("--first", action="store_true", help="Match first process only")
    parser.add_argument("--print", action="store_true", help="Print matching processes")

    parser.add_argument(
        "--interval",
        type=int,
        help="Monitor continuously every N seconds",
    )

    parser.add_argument(
        "--restart-cmd",
        type=str,
        help="Command to restart the service",
    )

    parser.add_argument("--log-file", type=str, help="Output log to log-file")
    parser.add_argument("--json", action="store_true", help="Output in json")
    parser.add_argument("--pretty", action="store_true", help="Output in pretty json")

    args_parsed = parser.parse_args(args)

    if args_parsed.pretty and not args_parsed.json:
        parser.error("--pretty requires --json")

    if args_parsed.first and not (args_parsed.name or args_parsed.port):
        parser.error("--first requires --name or --port")

    return args_parsed


# ----------------------------
# Process Filters
# ----------------------------


def get_self_and_parent_pids() -> set[int]:
    pids = set()
    p: psutil.Process | None = psutil.Process(os.getpid())

    while p:
        pids.add(p.pid)
        p = p.parent()

    return pids


def filter_by_pid(pid: int) -> Optional[psutil.Process]:
    try:
        return psutil.Process(pid)
    except psutil.Error:
        return None
    except (ValueError, TypeError) as e:
        print(f"Error pid filter: {e}")
        raise SystemExit(1)


def filter_by_name(name: str, first: bool = False) -> List[psutil.Process]:
    results = []
    ignore_pids = get_self_and_parent_pids()

    for proc in psutil.process_iter([NAME, CMDLINE]):
        try:
            if proc.pid in ignore_pids:
                continue

            proc_name = (proc.info[NAME] or "").lower()
            cmd = " ".join(proc.info[CMDLINE] or []).lower()

            # exact match of name means no more search
            if name == cmd:
                return [proc]

            # part of name match means more search
            if name in proc_name or name in cmd:
                results.append(proc)

                if first:
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return results


def filter_by_port(port: int, first: bool = False) -> List[psutil.Process]:
    results: set[psutil.Process] = set()
    ignore_pids = get_self_and_parent_pids()

    try:
        for conn in psutil.net_connections(kind="inet"):
            # skip if no address or wrong port
            if not conn.laddr or conn.laddr.port != port:
                continue

            pid = conn.pid

            # warn if port matches but could not retrieve pid
            if conn.laddr.port == port and pid is None:
                logging.error(
                    f"PIDERROR: Port Found - '{conn.laddr}' but PID is {pid}. Sign of PermissionError."
                )
                continue

            # skip kernel sockets or our own process tree
            if pid is None or pid in ignore_pids:
                continue

            try:
                proc = psutil.Process(pid)
                results.add(proc)

                if first:
                    break

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    except psutil.Error:
        pass

    return list(results)


# ----------------------------
# Restart Logic
# ----------------------------


def restart_service(command: str, timeout: int = 10) -> bool:
    try:
        logging.warning(f"Restarting service using: {command}")

        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            logging.info("Restart successful")
            return True

        logging.error(result.stderr.strip())
        return False

    except subprocess.TimeoutExpired:
        logging.error("Restart command timed out")
        return False

    except Exception as e:
        logging.error(f"Restart failed: {e}")
        return False


# ----------------------------
# Output
# ----------------------------


def output_processes(
    processes: List[psutil.Process],
    json_out: bool = False,
    pretty: bool = True,
    conn_port: int | None = None,
):
    if not processes:
        logging.error(f"OUTPUT: {NO_MATCH_FOUND}")
        return

    data: list[dict[str, Any]] = []

    for p in processes:
        try:
            # 1. Get the standard fields first
            proc_dict = p.as_dict(PROCESS_FIELDS)

            # 2. Try to get network info (the high-privilege part)
            try:
                conns = [
                    conn.laddr
                    for conn in p.net_connections(kind="inet")
                    if conn.laddr
                    and (conn_port is None or conn.laddr.port == conn_port)
                ]
                proc_dict[CONNECTIONS] = conns
            except psutil.AccessDenied as e:
                logging.error(
                    f"OUTPUT: Access Denied for PID {p.pid}: {e}. "
                    "Running with root privileges might help."
                )
                proc_dict[CONNECTIONS] = None

            data.append(proc_dict)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # If the process disappears or we can't even get basic info, skip it
            continue
        except psutil.Error:
            continue

    # Output section
    if json_out:
        indent = 4 if pretty else None
        print(json.dumps(data, indent=indent))
    else:
        # Renamed variable to 'item' to avoid Mypy type conflict with 'p'
        for item in data:
            print(item)


# ----------------------------
# Monitor Loop
# ----------------------------


def check_process(args: argparse.Namespace) -> List[psutil.Process]:

    if args.pid:
        proc = filter_by_pid(-2)
        # proc = filter_by_pid(args.pid)
        return [proc] if proc else []

    if args.name:
        return filter_by_name(args.name, args.first)

    if args.port:
        return filter_by_port(args.port, args.first)

    return []


def run_watchdog(args: argparse.Namespace):

    while True:
        processes = check_process(args)

        if processes:
            logging.info("Service healthy. No restart required.")
        else:
            logging.warning("Service not running")

            if args.restart_cmd:
                restart_service(args.restart_cmd)
        if args.print:
            output_processes(processes, args.json, args.pretty, args.port)

        if not args.interval:
            break

        time.sleep(args.interval)


# ----------------------------
# Main
# ----------------------------


def main():
    args = parse_args()
    log_file = args.log_file

    try:
        log_config(log_file, args.json)
        run_watchdog(args)
    except KeyboardInterrupt:
        logging.info("Watchdog stopped")
    except Exception:
        return


if __name__ == "__main__":
    main()
