import argparse, json, subprocess, sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--run',type=Path,required=True); a=ap.parse_args(); a.run.mkdir(parents=True,exist_ok=True)
    from src.preflight import build_preflight
    (a.run/'preflight.json').write_text(json.dumps(build_preflight(a.input),ensure_ascii=False,indent=2),encoding='utf-8')
    p=lambda *x: subprocess.run([sys.executable,*map(str,x)],cwd=Path(__file__).parents[1],check=True)
    p('src/aggregate_metrics.py',a.input,a.run/'channel_metrics.csv','--category-output',a.run/'category_metrics.csv')
    p('src/run_rules.py',a.run/'channel_metrics.csv',a.run/'rule_results.csv','--category-metrics',a.run/'category_metrics.csv','--json-output',a.run/'rule_results.json')
    from src.capability_facts import write_capability_facts
    write_capability_facts(a.run/'channel_metrics.csv',a.run/'category_metrics.csv',a.run/'facts.json',a.run/'capabilities.json')
    p('scripts/report_composer.py','--preflight',a.run/'preflight.json','--capabilities',a.run/'capabilities.json','--facts',a.run/'facts.json','--rules',a.run/'rule_results.json','--output',a.run/'report_model.json')
    import shutil; shutil.copyfile(a.run/'report_model.json',a.run/'semantic_blocks.json')
    p('scripts/semantic_blocks_to_docx.py','--input-blocks',a.run/'semantic_blocks.json','--output',a.run/'report.docx')
    print(a.run/'report.docx')
if __name__=='__main__': main()
