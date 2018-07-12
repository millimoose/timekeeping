#!/usr/bin/env python
from __future__ import division
from __future__ import print_function

import warnings

import sys
import argparse
from urllib2 import urlopen
from tempfile import TemporaryFile

import datetime
import re
from math import ceil

from collections import defaultdict as ddict, OrderedDict as odict
from operator import attrgetter
from contextlib import closing, contextmanager

with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=UserWarning)
    import icalendar

from dateutil.relativedelta import relativedelta

CALFILE_URL = 'https://p01-calendarws.icloud.com/ca/subscribe/1/NVzefG4vMPprqrm6yjay40vZHiAHuyF8BFkaBMgsqRkfhuyI8vTAMJp9T1ufUtLd2emy22MOXbzoeDIjvBTJg0T8lPwJ2SEA3xpRvqmUkVY'

_URL_PREFIX = re.compile(r'\w+://')


@contextmanager
def redirect_stdout(target):
    old = sys.stdout

    if isinstance(target, basestring):
        with open(target, 'a') as new:
            sys.stdout = new
    else:
        sys.stdout = target

    yield
    sys.stdout = old


@contextmanager
def squelch_stdout():
    with TemporaryFile() as target:
        with redirect_stdout(target):
            yield


def is_url(filename):
    return _URL_PREFIX.match(filename) is not None


def open_calfile(filename):
    if is_url(filename):
        return closing(urlopen(filename))
    else:
        return open(filename)


class TimezoneStripper(object):
    _BEGIN_VTIMEZONE = 'BEGIN:VTIMEZONE'
    _END_VTIMEZONE = 'END:VTIMEZONE'

    _in_timezone = False

    def __init__(self, lines):
        self.lines = lines

    def __iter__(self):
        for line in self.lines:
            _line = line.strip().upper()
            if _line == self._BEGIN_VTIMEZONE:
                self._in_timezone = True

            if not self._in_timezone:
                yield line
#                yield ''.join(c for c in line if ord(c) < 128)

            if _line == self._END_VTIMEZONE:
                self._in_timezone = False


def read_calfile(calfile):
    return ''.join(TimezoneStripper(calfile))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('calfile', nargs='?', default=CALFILE_URL, help='URL or path to ICS file', metavar="FILE")
    parser.add_argument('-m', '--month', type=int, metavar='MONTH', help='the month that you want to report',
                        default=None)
    parser.add_argument('-y', '--year', type=int, metavar='YEAR', help='the year that you want to report', default=None)
    parser.add_argument('-o', '--output', nargs='?', metavar='OUTFILE', help='save a report to this file',
                        const=Ellipsis, default=None)
    return parser.parse_args()


class MonthReport(object):
    def __init__(self, (year, month), events):
        self.year = year
        self.month = month
        self.events = list(events)

    _HALF_HOUR = datetime.timedelta(minutes=30)

    @classmethod
    def event_duration(cls, ev):
        """Return the event duration in hours, rounded up to the nearest half-hour"""
        duration = ev['DTEND'].dt - ev['DTSTART'].dt
        half_hours = duration.total_seconds() / cls._HALF_HOUR.total_seconds()
        return ceil(half_hours) / 2

    def period(self):
        return datetime.date(self.year, self.month, 1).strftime('%b %Y')

    def filename(self):
        return 'report-{}-{:02}.txt'.format(self.year, self.month)

    TASK_ID_RE = re.compile(r'#([\w\-_]+)')

    def task_breakdown(self):
        result = ddict(lambda: [])
        for ev in self.events:
            task_id = None
            m = self.TASK_ID_RE.match(ev['summary'].strip())
            if m is not None:
                task_id = m.group(1)
            result[task_id].append(ev)

        return odict(sorted(result.items()))

    @classmethod
    def sum_durations(cls, events):
        return sum(cls.event_duration(ev) for ev in events)

    def report_text(self):
        result = ['Report for {}'.format(self.period())]

        tasks = self.task_breakdown()
        other_events = []
        try:
            other_events = tasks.pop(None)
        except KeyError:
            pass
        result.append('=' * 8)
        total = 0

        for id, events in tasks.items():
            subtotal = self.sum_durations(events)
            total += subtotal
            result.append('#{}:\t{:.1f}h'.format(id, subtotal))

        if other_events:
            subtotal = self.sum_durations(other_events)
            total += subtotal
            result.append('Other:\t{:.1f}h'.format(subtotal))

        result.append('-' * 8)
        result.append("Total:\t{:.1f}h".format(total))
        return '\n'.join(result)


def main():
    args = parse_args()

    with open_calfile(args.calfile) as calfile:
        cal_string = read_calfile(calfile)

    with squelch_stdout():
        cal = icalendar.Calendar.from_ical(cal_string)

    events = (it for it in cal.walk() if it.name.upper() == 'VEVENT')

    get_year_month = attrgetter('year', 'month')
    report_date = datetime.date.today()

    rd = relativedelta()
    if args.year: rd.year = args.year
    if args.month:
        if args.month > 0:
            rd.month = args.month
        else:
            assert args.month < 0
            rd.months = args.month
    report_date += rd

    year_month = get_year_month(report_date)
    report = MonthReport(year_month,
                         (ev for ev in events
                             if get_year_month(ev['DTSTART'].dt) == year_month))

    report_text = report.report_text()

    if args.output:
        output = args.output
        if output is Ellipsis:
            output = report.filename()
        with open(output, 'w') as output_file:
            print(report_text, file=output_file)

    print(report_text)


if __name__ == '__main__':
    main()
