import json,sys,urllib.request
def rpc(method,**p):
    r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8089/jsonrpc',json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':p}).encode(),{'Content-Type':'application/json'}),timeout=120)
    return json.loads(r.read())
def ls(path,n=8):
    r=rpc('Files.GetDirectory',directory=path,media='files',properties=['title','plot'])
    if 'error' in r: print('ERR',path,r['error']); return []
    f=r['result'].get('files') or []
    print('%s -> %d items'%(path,len(f)))
    for x in f[:n]: print('   ',x['label'][:90],'|',x['file'][:100])
    return f
if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for p in sys.argv[1:]: ls(p)
