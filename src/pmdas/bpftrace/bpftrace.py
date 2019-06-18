#
# Copyright (c) 2019 Red Hat.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
"""bpftrace"""

import subprocess
import signal
import re
from threading import Thread, Lock
from queue import Queue
from copy import deepcopy


class BPFtraceError(Exception):
    """BPFtrace general error"""

class BPFtrace:
    """class for interacting with bpftrace"""
    def __init__(self, log, script):
        self.log = log
        self.script = script

        self.pid = None
        self.probes = None

        self.info_q = Queue()
        self.lock = Lock()
        self._data = {}

    @property
    def started(self):
        """returns true if bpftrace was started"""
        return bool(self.pid)

    @classmethod
    def parse_histogram(cls, lines_it):
        """parse a histogram"""
        multipliers = {
            '': 1,
            'K': 1024,
            'M': 1024 * 1024
        }

        histogram = {}
        for hist_line in lines_it:
            hist_negative = re.match(r'\(..., 0\)\s+(\d+)', hist_line)
            hist_single = re.match(r'\[(\d+)]\s+(\d+)', hist_line)
            hist_m = re.match(r'\[(\d+)(.?), (\d+)(.?)\)\s+(\d+)', hist_line)
            if hist_negative:
                histogram['-1'] = hist_negative.group(1)
            elif hist_single:
                bucket, val = hist_single.groups()
                if bucket in ['0', '1']:
                    histogram['0-1'] = histogram.get('0-1', 0) + int(val)
                else:
                    raise BPFtraceError("can't parse histogram output")
            elif hist_m:
                low, low_u, high, high_u, val = hist_m.groups()
                low = int(low) * multipliers[low_u]
                high = int(high) * multipliers[high_u] - 1

                histogram['{}-{}'.format(low, high)] = int(val)                            
            else:
                break
        return histogram
                
    @classmethod
    def parse_variables(cls, lines):
        """parse variables from bpftrace output"""
        variables = {}
        lines_it = iter(lines)
        for line in lines_it:
            var_m = re.match(r'(@.*?)(\[.+?\])?: (.*)', line)
            if var_m:
                name, key, val = var_m.groups()
                if val:
                    if val.isnumeric():
                        val = int(val)
                    if key:
                        key = key[1:-1]
                        if name not in variables:
                            variables[name] = {}
                        variables[name][key] = val
                    else:
                        variables[name] = val
                else:
                    variables[name] = cls.parse_histogram(lines_it)
                    
        return variables

    def process_output(self):
        """process stdout and stderr of running bpftrace process"""
        info_lines = []
        data_lines = []

        # parse info lines (Attaching X probes, error messages)
        for line in self.process.stdout:
            line = line.decode('utf-8')
            if '@' in line:
                data_lines.append(line)
                break
            else:
                info_lines.append(line)
        self.info_q.put(info_lines)

        # parse data lines
        for line in self.process.stdout:
            line = line.decode('utf-8')
            if line != '###\n':
                data_lines.append(line)
            else:
                with self.lock:
                    self._data = self.parse_variables(data_lines)
                data_lines = []

    def prepare_script(self):
        """prepares bpftrace script (add continuous output)"""
        variables = re.findall(r'(@.*?)(\[.+?\])?\s*=', self.script)
        if variables:
            print_st = ' '.join(['print({});'.format(var) for var, key in variables])
            self.script = self.script + ' interval:s:1 {{ {} printf("###\\n"); }}'.format(print_st)
        else:
            raise BPFtraceError("no global bpftrace variable found, please include "
                                "at least one global variable in your script")

    def start(self):
        """starts bpftrace in the background, waits until first data arrives or an error occurs"""
        if self.started:
            raise Exception("bpftrace already started")

        self.prepare_script()
        self.process = subprocess.Popen(['bpftrace', '-e', self.script],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.pid = self.process.pid

        # with daemon=False, atexit doesn't work
        self.process_output_thread = Thread(target=self.process_output, daemon=True)
        self.process_output_thread.start()

        # block until we get the first data output or an error
        info_lines = self.info_q.get()

        if len(info_lines) == 1 and 'Attaching' in info_lines[0]:
            match = re.match(r'Attaching (\d+) probes?\.\.\.', info_lines[0])
            if match:
                self.probes = int(match.group(1))
                self.log("started bpftrace -e '{}', "
                         "PID: {}, #probes: {}".format(self.script, self.pid, self.probes))
        else:
            raise BPFtraceError("bpftrace error: {}".format(''.join(info_lines).rstrip()))

    def data(self):
        """returns latest output"""
        if not self.started:
            raise Exception("bpftrace is not started")

        with self.lock:
            return self._data

    def stop(self, wait=False):
        """stop bpftrace process"""
        if not self.started:
            raise Exception("bpftrace is not started")

        self.log("send stop signal to bpftrace process {}, "
                 "wait for termination: {}".format(self.pid, wait))
        self.process.send_signal(signal.SIGINT)
        if wait:
            # wait until process terminates
            self.process.communicate()
            self.log("process stopped")
