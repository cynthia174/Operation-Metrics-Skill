"""Legacy standalone external-model experiment; not the formal Skill path.

Formal execution pauses for the host Agent after Module Contexts.
"""
import argparse, json, subprocess, sys, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--run',type=Path,required=True); a=ap.parse_args(); a.run.mkdir(parents=True,exist_ok=True); root=Path(__file__).parents[1]; py=sys.executable; run=a.run
 from src.preflight import build_preflight
 (run/'preflight.json').write_text(json.dumps(build_preflight(a.input),ensure_ascii=False,indent=2),encoding='utf-8')
 def p(*args): subprocess.run([py,*map(str,args)],cwd=root,check=True)
 p('src/aggregate_metrics.py',a.input,run/'channel_metrics.csv','--category-output',run/'category_metrics.csv')
 p('src/run_rules.py',run/'channel_metrics.csv',run/'rule_results.csv','--category-metrics',run/'category_metrics.csv','--json-output',run/'rule_results.json')
 from src.capability_facts import write_capability_facts
 write_capability_facts(run/'channel_metrics.csv',run/'category_metrics.csv',run/'facts.json',run/'capabilities.json')
 p('scripts/build_module_contexts.py','--preflight',run/'preflight.json','--capabilities',run/'capabilities.json','--facts',run/'facts.json','--rules',run/'rule_results.json','--output-dir',run/'contexts')
 manifest={'run_id':str(uuid.uuid4()),'status':'RUNNING','stages':{}}
 (run/'prompt_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 try:
  for m in ('channel','product','efficiency','growth_quality','summary'):
   p('scripts/prompt_runner.py','--module',m,'--prompt-dir',root/'prompts','--context-dir',run/'contexts','--output-dir',run/'modules','--manifest',run/'prompt_manifest.json')
 except Exception:
  manifest=json.loads((run/'prompt_manifest.json').read_text(encoding='utf-8')); manifest['status']='FAILED'; (run/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); raise
 p('scripts/assemble_report.py','--channel',run/'modules/channel.md','--product',run/'modules/product.md','--efficiency',run/'modules/efficiency.md','--growth-quality',run/'modules/growth_quality.md','--summary',run/'modules/summary.md','--output',run/'semantic_blocks.json')
 p('scripts/semantic_blocks_to_docx.py','--input-blocks',run/'semantic_blocks.json','--output',run/'report.docx')
 manifest=json.loads((run/'prompt_manifest.json').read_text(encoding='utf-8')); manifest['status']='PASS'; (run/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print(run/'report.docx')
if __name__=='__main__': main()
