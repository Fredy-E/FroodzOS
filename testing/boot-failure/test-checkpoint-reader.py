#!/usr/bin/env python3
"""Windows tests for the read-only firmware recovery script; synthetic records."""
import json, subprocess, tempfile
from pathlib import Path
P=Path('D:/CachyOS-ARM64/testing/boot-failure')
results=[]
with tempfile.TemporaryDirectory(prefix='kestrel-reader-',dir='C:/Users/USER/AppData/Local/hermes/cache/scratch') as tmp:
 for name,expected in [('0',0),('1',0),('2',0),('3',0),('corrupt',2),('truncated',2)]:
  out=Path(tmp)/name
  r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(P/'Read-KestrelCheckpoint.ps1'),'-InputFile',str(P/'checkpoint-reader-fixtures'/(name+'.bin')),'-OutputDirectory',str(out)],capture_output=True,text=True)
  if r.returncode!=expected: raise RuntimeError(f'{name} expected={expected} rc={r.returncode}\n{r.stdout}\n{r.stderr}')
  report=json.loads((out/'report.json').read_text(encoding='utf-8-sig'))
  assert report['firmware_writes']==0 and report['input_is_fixture']
  results.append({'fixture':name,'exit':r.returncode,'status':report['records'][0]['status']})
report={'passed':True,'tests':results,'firmware_calls':0,'note':'Synthetic fixtures; no native capture claimed.'}
(P/'checkpoint-reader-test-result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
