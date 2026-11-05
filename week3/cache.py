"""Bounded exact JSON caches. Versions define validity; TTL bounds retention."""
import hashlib
import json
import threading
import time
from collections import OrderedDict
from pathlib import Path

import anyio

from week1.responses import guard
from week2.contracts import descriptor, NAMES, validate_arguments, validate_result


def identity(value):
    guard(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_version(path, limit=16*1024*1024):
    with Path(path).open('rb') as stream:
        data=stream.read(limit+1)
    if len(data)>limit:
        raise ValueError('source_too_large')
    return hashlib.sha256(data).hexdigest()


class CacheToolError(ValueError):
    def __init__(self,bundle):
        self.bundle=bundle
        super().__init__('tool_unavailable')


class ExactCache:
    def __init__(self, *, ttl=300, entries=1024, byte_limit=16*1024*1024, clock=time.monotonic):
        if ttl<=0 or entries<1 or byte_limit<1:
            raise ValueError('invalid_cache_limits')
        self.ttl, self.capacity, self.byte_limit, self.clock=ttl, entries, byte_limit, clock
        self.items=OrderedDict(); self.bytes=0; self.pending=set(); self.lock=threading.Lock()

    def get(self,key):
        with self.lock:
            item=self.items.get(key)
            if item is None:return None
            data,created,expires=item
            if self.clock()>=expires:
                self.items.pop(key);self.bytes-=len(data)
                return None
            self.items.move_to_end(key)
            value=json.loads(data)
            guard(value)
            return value, {'age_ms':round((self.clock()-created)*1000,3),'ttl_seconds':self.ttl}

    def put(self,key,value):
        guard(value)
        data=json.dumps(value,sort_keys=True,allow_nan=False).encode()
        if len(data)>self.byte_limit:return False
        with self.lock:
            old=self.items.pop(key,None)
            if old:self.bytes-=len(old[0])
            while self.items and (len(self.items)>=self.capacity or self.bytes+len(data)>self.byte_limit):
                _,old=self.items.popitem(last=False);self.bytes-=len(old[0])
            now=self.clock();self.items[key]=(data,now,now+self.ttl);self.bytes+=len(data)
        return True

    def reserve(self,key):
        with self.lock:
            if key in self.pending:return False
            if len(self.pending)>=self.capacity:raise ValueError('cache_busy')
            self.pending.add(key);return True

    def release(self,key):
        with self.lock:self.pending.discard(key)

    def clear(self):
        with self.lock:self.items.clear();self.bytes=0

    def load(self,key,compute,valid=lambda:True):
        started=time.monotonic()
        while True:
            found=self.get(key)
            if found:
                if not valid():raise ValueError('source_changed')
                return found[0],dict(found[1],outcome='hit',duration_ms=round((time.monotonic()-started)*1000,3))
            if self.reserve(key):break
            if time.monotonic()-started>12:raise ValueError('cache_wait_timeout')
            time.sleep(.005)
        try:
            # Another worker may have published between lookup and reservation.
            found=self.get(key)
            if found:
                if not valid():raise ValueError('source_changed')
                return found[0],dict(found[1],outcome='hit',duration_ms=round((time.monotonic()-started)*1000,3))
            value=compute()
            if not valid():raise ValueError('source_changed')
            stored=self.put(key,value)
            return value,{'outcome':'miss','stored':stored,'age_ms':0,'ttl_seconds':self.ttl,'duration_ms':round((time.monotonic()-started)*1000,3)}
        finally:self.release(key)

    async def aload(self,key,compute,valid=lambda:True):
        started=time.monotonic()
        while True:
            found=self.get(key)
            if found:
                if not valid():raise ValueError('source_changed')
                return found[0],dict(found[1],outcome='hit',duration_ms=round((time.monotonic()-started)*1000,3))
            if self.reserve(key):break
            if time.monotonic()-started>12:raise ValueError('cache_wait_timeout')
            await anyio.sleep(.005)
        try:
            found=self.get(key)
            if found:
                if not valid():raise ValueError('source_changed')
                return found[0],dict(found[1],outcome='hit',duration_ms=round((time.monotonic()-started)*1000,3))
            value=await compute()
            if not valid():raise ValueError('source_changed')
            stored=self.put(key,value)
            return value,{'outcome':'miss','stored':stored,'age_ms':0,'ttl_seconds':self.ttl,'duration_ms':round((time.monotonic()-started)*1000,3)}
        finally:self.release(key)


class WorkflowCaches:
    def __init__(self, *, ttl=300, clock=time.monotonic):
        self.tools=ExactCache(ttl=ttl,clock=clock)
        self.retrieval=ExactCache(ttl=ttl,clock=clock)
        self.embeddings=ExactCache(ttl=86400,clock=clock)

    def clear(self):
        for cache in (self.tools,self.retrieval,self.embeddings):cache.clear()

    @staticmethod
    def tool_version():
        from week2 import tools
        return identity([file_version(tools.CATALOG_PATH,1024*1024),
            file_version(Path(tools.__file__)),file_version(Path(__file__).parents[1]/'week2/contracts.py'),
            file_version(Path(__file__).parents[1]/'week2/mcp_server.py'),
            file_version(Path(__file__).parents[1]/'week2/mcp_client.py'),
            [descriptor(n) for n in NAMES]])

    async def call_tools(self,calls,*,scope,runner):
        if not isinstance(calls,list) or not 1<=len(calls)<=2 or len({n for n,_ in calls})!=len(calls):
            raise ValueError('invalid_calls')
        version=self.tool_version();outputs={};events=[];cache_events=[]
        metrics={'attempted':0,'failed':0,'status':'measured'}
        for name,args in calls:
            validate_arguments(name,args)
            key=identity([scope,version,name,args])
            actual=[]
            async def compute():
                bundle=await runner([(name,args)])
                if bundle['status']!='ok' or set(bundle['outputs'])!={name}:
                    raise CacheToolError(bundle)
                value=bundle['outputs'][name]
                validate_result(name,args['service_name'],value)
                if value['status']!='ok':raise CacheToolError(bundle)
                measured=bundle.get('metrics')
                if measured and measured.get('status')=='measured' and metrics['status']=='measured':
                    metrics['attempted']+=measured['attempted'];metrics['failed']+=measured['failed']
                else:metrics.update(attempted=None,failed=None,status='unavailable')
                actual.extend(bundle['events'])
                return value
            try:
                value,event=await self.tools.aload(key,compute,lambda:self.tool_version()==version)
            except CacheToolError as error:
                measured=error.bundle.get('metrics',{})
                if measured.get('status')=='measured' and metrics['status']=='measured':
                    error.bundle['metrics']={k:metrics[k]+measured[k] for k in ('attempted','failed')}
                    error.bundle['metrics']['status']='measured'
                raise
            validate_result(name,args['service_name'],value)
            outputs[name]=value
            cache_events.append(dict(event,layer='tool',tool=name,source_version=version))
            events.extend(actual)
            if event['outcome']=='hit':
                events.append({'event':'cache_result','tool':name,'source_version':version,
                    'input':args,'output':value})
        if self.tool_version()!=version:raise ValueError('source_changed')
        return {'status':'ok','outputs':outputs,'events':events,'cache_events':cache_events,'metrics':metrics}

    @staticmethod
    def retrieval_version(index_path):
        from week1 import retrieval as r
        db,meta=r._open_index(index_path)
        db.close()
        docs=r._documents(Path(meta['corpus_dir']))
        if r._corpus_digest(docs)!=meta['corpus_digest']:
            raise ValueError('source_changed')
        return identity([meta,file_version(index_path)])

    def retrieve(self,query,index_path,*,limit,service,scope,events):
        from week1 import retrieval as r
        source=self.retrieval_version(index_path);encoder=r._default_encoder();fingerprint=r._encoder_identity(encoder)
        key=identity([scope,source,fingerprint,query,service,limit])
        caches=self
        class Encoder:
            _cra2_fingerprint=fingerprint
            def query_embed(self,text):
                import numpy as np
                def compute():return [v.tolist() for v in r._embed(encoder,'query_embed',text)]
                value,event=caches.embeddings.load(identity([scope,fingerprint,text]),compute)
                events.append(dict(event,layer='query_embedding',source_version=fingerprint))
                return iter([np.array(v,dtype=np.float32) for v in value])
        def compute():return r.search(query,index_path,limit=limit,service=service,encoder=Encoder())
        value,event=self.retrieval.load(key,compute,lambda:self.retrieval_version(index_path)==source)
        guard(value)
        events.append(dict(event,layer='retrieval',source_version=source))
        return value

    def sources_current(self,events,index_path):
        for layer,get_version in [('tool',self.tool_version),('retrieval',lambda:self.retrieval_version(index_path))]:
            versions={e['source_version'] for e in events if e['layer']==layer}
            if versions and versions!={get_version()}:return False
        return True
