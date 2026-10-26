"""Explicit edit boundaries and source-time provenance for prepared match clips."""
from bisect import bisect_right
from functools import lru_cache
import json
import math
from pathlib import Path

FORMAT = 'rodri_edit_timeline_v1'


class EditTimeline:
    def __init__(self, metadata):
        if metadata.get('format') != FORMAT:
            raise ValueError('Unsupported edit timeline')
        self.metadata = metadata
        self.segments = metadata['segments']
        self.starts = []
        previous = 0.
        for row in self.segments:
            a, b = row['clip_start_seconds'], row['clip_end_seconds_exclusive']
            sa, sb = row['source_start_seconds'], row['source_end_seconds_exclusive']
            if not all(math.isfinite(x) for x in [a,b,sa,sb]) or abs(a-previous)>1e-6 or b<=a or sa<0 or abs((sb-sa)-(b-a))>1e-6:
                raise ValueError('Invalid or incomplete edit timeline')
            self.starts.append(a)
            previous = b
        if not self.segments:
            raise ValueError('Empty edit timeline')

    def segment(self, timestamp):
        if not math.isfinite(timestamp):
            raise ValueError('Invalid timestamp')
        i = bisect_right(self.starts, timestamp + 1e-8)-1
        if i < 0 or timestamp >= self.segments[i]['clip_end_seconds_exclusive']-1e-8:
            raise ValueError('Timestamp outside edit timeline')
        return self.segments[i]

    def crosses(self, observation, target):
        return self.segment(observation) is not self.segment(target)

    def source_time(self, timestamp):
        row = self.segment(timestamp)
        return row['source_start_seconds']+timestamp-row['clip_start_seconds']


@lru_cache(maxsize=64)
def _load(path, mtime, size):
    return EditTimeline(json.loads(Path(path).read_text()))


def timeline_for(path):
    sidecar = Path(str(path)+'.edits.json')
    if not sidecar.exists():
        return None
    stat = sidecar.stat()
    return _load(str(sidecar.resolve()), stat.st_mtime_ns, stat.st_size)


def history_start(path, timestamp):
    timeline = timeline_for(path)
    return timeline.segment(timestamp)['clip_start_seconds'] if timeline else 0.


def validate_observation(path, row):
    timeline = timeline_for(path)
    if timeline and timeline.crosses(row['observation_seconds'], row['target_seconds']):
        raise ValueError('Observation and future target cross a removed section')
    if timeline and row['match_id'] != timeline.metadata['match_id']:
        raise ValueError('All edited clips of one match must share the source match ID')
    return timeline
