"""Bounded private metadata only. No questions, notes, prompts or raw outputs."""
import json
import os
import sqlite3
import stat
from pathlib import Path

from week1.responses import guard

ROOT=Path(__file__).resolve().parents[1]
STAGES={'classify','legacy','retrieve','tools','compose','output_guard','memory_read','memory_write',
    'rail_input','rail_context','rail_output','cache_query_embedding','cache_retrieval','cache_tool','reviewer'}
TRANSPORTS={'cli','browser','slack','evaluation'}


class TelemetryUnavailable(ValueError):pass


def compact(trace):
    record={k:trace[k] for k in ('request_id','transport','status','duration_ms')}
    record.update(provider_attempted=bool(trace.get('request_attempted')),
        mcp=trace.get('mcp',{'status':'not_accessed','attempted':0,'failed':0}),
        rail_counts={outcome:sum(e['outcome']==outcome for e in trace.get('rails',[]))
            for outcome in ('allow','block','unavailable')},
        cache_counts={outcome:sum(e['outcome']==outcome for e in trace.get('cache',[]))
            for outcome in ('hit','miss')},
        spans=[{k:s[k] for k in ('stage','duration_ms','outcome')} for s in trace.get('spans',[]) if s['stage'] in STAGES])
    guard(record)
    if record['transport'] not in TRANSPORTS or len(record['request_id'])!=32:
        raise TelemetryUnavailable('invalid_metadata')
    raw=json.dumps(record,allow_nan=False)
    if len(raw.encode())>8192:raise TelemetryUnavailable('metadata_too_large')
    return record


class TelemetryStore:
    def __init__(self,path,*,max_rows=2000,max_bytes=8*1024*1024):
        self.path=Path(path);self.max_rows=max_rows;self.max_bytes=max_bytes

    def write(self,trace):
        try:
            raw=json.dumps(compact(trace),allow_nan=False)
            p=self.path
            if p.is_symlink() or not any(p.resolve().is_relative_to(r) for r in (ROOT,Path('/tmp').resolve())):
                raise TelemetryUnavailable('invalid_store')
            p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if stat.S_IMODE(p.parent.stat().st_mode)!=0o700 or p.parent.stat().st_uid!=os.getuid():
                raise TelemetryUnavailable('invalid_store')
            new=not p.exists()
            if new:
                fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
            if (stat.S_IMODE(p.stat().st_mode)!=0o600 or p.stat().st_uid!=os.getuid()
                    or p.stat().st_size>self.max_bytes):raise TelemetryUnavailable('invalid_store')
            db=sqlite3.connect(p,timeout=.2)
            try:
                db.execute('PRAGMA trusted_schema=OFF')
                if new:
                    with db:
                        db.execute('CREATE TABLE requests (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
                        db.execute('PRAGMA application_id=1129464116')
                objects=list(db.execute("SELECT type,name FROM sqlite_master WHERE type!='index'"))
                if (objects!=[('table','requests')] or db.execute('PRAGMA application_id').fetchone()[0]!=1129464116
                        or db.execute('SELECT count(*) FROM requests').fetchone()[0]>=self.max_rows
                        or p.stat().st_size+len(raw.encode())+8192>self.max_bytes):
                    raise TelemetryUnavailable('store_full_or_invalid')
                with db:db.execute('INSERT INTO requests VALUES (?,?)',(trace['request_id'],raw))
            finally:db.close()
        except Exception:
            raise TelemetryUnavailable('telemetry_unavailable') from None
