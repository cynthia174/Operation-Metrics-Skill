"""Optional standalone external adapter; not used by the formal Skill path.

The formal Prompt Runner is the host Agent, as defined in SKILL.md. This file
is retained only for explicit standalone integrations and must never be added
to the Skill execution plan.
"""
import argparse, json, os, time, urllib.request
from pathlib import Path

def call_model(prompt, model, base, token):
 openrouter='openrouter.ai' in base
 body=json.dumps({'model':model,'max_tokens':4000,'messages':[{'role':'user','content':prompt}]}).encode()
 endpoint='/v1/chat/completions' if openrouter else '/v1/messages'
 headers={'content-type':'application/json','Authorization':'Bearer '+token} if openrouter else {'content-type':'application/json','x-api-key':token,'anthropic-version':'2023-06-01'}
 req=urllib.request.Request(base.rstrip('/')+endpoint,data=body,headers=headers)
 with urllib.request.urlopen(req,timeout=120) as res: data=json.loads(res.read().decode())
 if openrouter: return data.get('choices',[{}])[0].get('message',{}).get('content','')
 content=data.get('content',[]); return ''.join(x.get('text','') for x in content if isinstance(x,dict))

def run_one(module, prompt_dir, context_dir, output_dir, manifest):
 started=time.time(); prompt_file=prompt_dir/(module+'.md'); context_file=context_dir/(module+'.json'); output_file=output_dir/(module+'.md')
 record={'status':'RUNNING','prompt_file':str(prompt_file),'context_file':str(context_file),'output_file':str(output_file),'started_at':started,'model':os.getenv('PROMPT_MODEL'),'provider':os.getenv('PROMPT_PROVIDER','anthropic-compatible')}
 manifest[module]=record
 try:
  model=os.getenv('PROMPT_MODEL','anthropic/claude-sonnet-4'); token=os.getenv('ANTHROPIC_AUTH_TOKEN'); base=os.getenv('ANTHROPIC_BASE_URL')
  if not model or not token or not base: raise RuntimeError('no usable model client configuration: PROMPT_MODEL, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL required')
  shared=(prompt_dir/'shared.md').read_text(encoding='utf-8'); prompt=shared+'\n\n'+prompt_file.read_text(encoding='utf-8')+'\n\nEVIDENCE_CONTEXT:\n'+context_file.read_text(encoding='utf-8')
  text=call_model(prompt,model,base,token)
  if not text.strip(): raise RuntimeError('model returned empty output')
  output_file.write_text(text,encoding='utf-8'); record.update(status='PASS',finished_at=time.time(),output_size=len(text))
 except Exception as e:
  record.update(status='FAILED',finished_at=time.time(),output_size=0,error=str(e)); raise

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--module',required=True); ap.add_argument('--prompt-dir',type=Path,required=True); ap.add_argument('--context-dir',type=Path,required=True); ap.add_argument('--output-dir',type=Path,required=True); ap.add_argument('--manifest',type=Path,required=True); a=ap.parse_args()
 manifest=json.loads(a.manifest.read_text(encoding='utf-8')) if a.manifest.exists() else {}
 a.output_dir.mkdir(parents=True,exist_ok=True)
 try: run_one(a.module,a.prompt_dir,a.context_dir,a.output_dir,manifest)
 finally: a.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
