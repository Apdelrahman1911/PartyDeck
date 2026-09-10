#!/usr/bin/env python3
from pathlib import Path
import datetime,hashlib,json,os,re,subprocess,sys,time

base=Path(__file__).resolve().parents[1]
branch,name=sys.argv[1:3]
assert branch in ('baseline','candidate')
project=base/branch
binary=Path('/opt/partydeck-godot/godot')
output=base/'evidence'/branch/name
output.mkdir(parents=True,exist_ok=False)
engine_args=[str(binary),'--path',str(project),'--audio-driver','Dummy','--log-file',str(output/'engine.log')]
options={
 'redraw':('three_d_redraw_check.gd',['--check-fixture='+str(base/'fixtures/launch-3d.json')]),
 'terminal-return':('terminal_return_render_check.gd',['--check-fixtures='+str(base/'fixtures')]),
 'portrait':('three_d_scene_check.gd',['--check-fixture='+str(base/'fixtures/launch-3d.json'),'--check-width=390','--check-height=844','--check-text-scale=1']),
 'landscape':('three_d_scene_check.gd',['--check-fixture='+str(base/'fixtures/launch-3d.json'),'--check-width=844','--check-height=390','--check-text-scale=1']),
 'large-text':('three_d_scene_check.gd',['--check-fixture='+str(base/'fixtures/launch-3d.json'),'--check-width=390','--check-height=844','--check-text-scale=2','--check-touch-drag=true']),
 'round-ended':('three_d_scene_check.gd',['--check-fixture='+str(base/'fixtures/round-ended-launch-3d.json'),'--check-width=390','--check-height=844','--check-text-scale=1']),
 'resource-reuse':(str(base/'receipts/resource_reuse_check.gd'),['--check-fixture='+str(base/'fixtures/launch-3d.json')]),
}
if name=='import':
    command=['flock','-w','45','/tmp/partydeck-godot.lock']+engine_args+['--headless','--editor','--import']
else:
    script,args=options[name]
    script_path=script if script.startswith('/') else 'res://tests/'+script
    command=['flock','-w','45','/tmp/partydeck-godot.lock','xvfb-run','-a','-s','-screen 0 1280x1024x24']+engine_args+['--rendering-method','gl_compatibility','--rendering-driver','opengl3','--script',script_path,'--','--manual-bridge','--check-output='+str(output)]+args
started=time.monotonic()
environment=os.environ.copy()
environment['GODOT_SILENCE_ROOT_WARNING']='1'
environment['LIBGL_ALWAYS_SOFTWARE']='1'
code=None; timed_out=False
with (output/'stdout.log').open('wb') as stdout,(output/'stderr.log').open('wb') as stderr:
    try:
        result=subprocess.run(command,stdout=stdout,stderr=stderr,env=environment,timeout=180)
        code=result.returncode
    except subprocess.TimeoutExpired:
        timed_out=True
logs='\n'.join(path.read_text(errors='replace') for path in (output/'stdout.log',output/'stderr.log'))
errors=[line for line in logs.splitlines() if re.search(r'(^|\s)(SCRIPT ERROR:|ERROR:|Parse Error:)',line)]
receipt={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'environment_overrides':{'GODOT_SILENCE_ROOT_WARNING':'1','LIBGL_ALWAYS_SOFTWARE':'1'},'exit_code':code,'timed_out':timed_out,'elapsed_seconds':time.monotonic()-started,'scope':'Desktop source validation only; elapsed time is check duration, not native entry timing. No export or shared project execution.','binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'source_hashes':{rel:hashlib.sha256((project/rel).read_bytes()).hexdigest() for rel in ('project.godot','presentations/three_d/table.gd','presentations/three_d/card_3d.gd')},'engine_errors':errors}
report=output/'report.json'
if report.exists():
    report_data=json.loads(report.read_text())
    receipt['reported_result']=report_data.get('result')
    receipt['checks']=len(report_data.get('checks',[]))
    receipt['failed_checks']=[check for check in report_data.get('checks',[]) if not check.get('passed',False)]
    receipt['report_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
receipt['passed']=code==0 and not timed_out and not errors and (name=='import' or receipt.get('reported_result')=='passed')
(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'branch':branch,'check':name,'passed':receipt['passed'],'exit_code':code,'reported_result':receipt.get('reported_result'),'checks':receipt.get('checks'),'errors':errors,'evidence':str(output)}),flush=True)
if not receipt['passed']:
    print(logs[-6000:],flush=True)
    sys.exit(1)
