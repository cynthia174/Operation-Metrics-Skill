"""Canonical Integration entrypoint: preflight, one approval, autonomous run."""
from pathlib import Path
import hashlib, uuid
import json, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.preflight import build_preflight, write_preflight
from scripts.workflow_runner import run
from scripts.run_manifest import safe_load, safe_write, now

ROOT=Path(__file__).resolve().parents[1]; PY=sys.executable
def make_plan(root=ROOT, input_path=None):
    rt=root/'outputs/runtime'; rt.mkdir(parents=True,exist_ok=True); stages=[]
    input_path = input_path or root/'_input_vol03.xlsx'
    def add(sid, executor, outputs, validator='files_exist'):
        stages.append({'id':sid,'depends_on':[] if not stages else [stages[-1]['id']], 'executor':executor,'outputs':outputs,'validator':validator,'retry_policy':{'max_attempts':1}})
    add('preflight',[PY,'-m','src.preflight',str(input_path),'--output',str(rt/'preflight.json')],['outputs/runtime/preflight.json'],'json')
    add('metrics',[PY,'src/aggregate_metrics.py',str(input_path),str(rt/'channel_metrics.csv'),'--category-output',str(rt/'category_metrics.csv')],['outputs/runtime/channel_metrics.csv','outputs/runtime/category_metrics.csv'])
    add('rules',[PY,'src/run_rules.py',str(rt/'channel_metrics.csv'),str(rt/'rule_results.csv'),'--category-metrics',str(rt/'category_metrics.csv'),'--json-output',str(rt/'rule_results.json')],['outputs/runtime/rule_results.csv','outputs/runtime/rule_results.json'],'rule_result')
    add('fact_qa',{'callable':'scripts.integration_adapters:fact_qa'},['outputs/runtime/fact_qa.json'],'qa')
    add('capability_facts',[PY,'-c',"from pathlib import Path; from src.capability_facts import write_capability_facts; r=Path('outputs/runtime'); write_capability_facts(r/'channel_metrics.csv',r/'category_metrics.csv',r/'facts.json',r/'capabilities.json')"],['outputs/runtime/facts.json','outputs/runtime/capabilities.json'],'json')
    add('module_contexts',[PY,'scripts/build_module_contexts.py','--preflight',str(rt/'preflight.json'),'--capabilities',str(rt/'capabilities.json'),'--facts',str(rt/'facts.json'),'--rules',str(rt/'rule_results.json'),'--output-dir',str(rt/'contexts')],['outputs/runtime/contexts/channel.json','outputs/runtime/contexts/product.json','outputs/runtime/contexts/efficiency.json','outputs/runtime/contexts/growth_quality.json','outputs/runtime/contexts/summary.json'],'files_exist')
    for module, prompt_file, context_file in (
        ('channel','channel.md','channel.json'), ('product','product.md','product.json'),
        ('efficiency','efficiency.md','efficiency.json'), ('growth_quality','growth-quality.md','growth_quality.json'),
        ('summary','summary.md','summary.json')):
        stages.append({'id':module+'_prompt','kind':'agent_interaction','depends_on':[stages[-1]['id']], 'prompt_file':str(root/'prompts'/prompt_file), 'context_file':str(rt/'contexts'/context_file), 'output_file':str(rt/'modules'/(module+'.md')), 'manifest':'outputs/runtime/prompt_manifest.json'})
    add('assemble_report',[PY,'scripts/assemble_report.py','--channel',str(rt/'modules/channel.md'),'--product',str(rt/'modules/product.md'),'--efficiency',str(rt/'modules/efficiency.md'),'--growth-quality',str(rt/'modules/growth_quality.md'),'--summary',str(rt/'modules/summary.md'),'--output',str(rt/'semantic_blocks.json')],['outputs/runtime/semantic_blocks.json'],'semantic_blocks')
    add('docx',[PY,'scripts/semantic_blocks_to_docx.py','--input-blocks',str(rt/'semantic_blocks.json'),'--output',str(rt/'report.docx')],['outputs/runtime/report.docx','outputs/runtime/report.qa.json'],'docx_qa')
    add('ooxml_qa',{'callable':'scripts.integration_adapters:ooxml'},['outputs/runtime/ooxml_qa.json'],'qa')
    add('artifact_lineage_qa',{'callable':'scripts.integration_adapters:artifact_lineage_qa'},['outputs/runtime/artifact_lineage_qa.json','outputs/runtime/run_manifest.json'],'qa')
    return {'plan_version':'integration-1.0','workflow':'operation_metrics','goal':'Raw Excel to validated DOCX report','requires_user_approval':True,'status':'AWAITING_PLAN_APPROVAL','stages':stages,'definition_of_done':{'required_stages':[x['id'] for x in stages]}}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'_input_vol03.xlsx')
    args = parser.parse_args()
    rt=ROOT/'outputs/runtime'; write_preflight(build_preflight(args.input),rt/'preflight.json'); plan=make_plan(input_path=args.input)
    run_id = str(uuid.uuid4())
    for stage in plan['stages']: stage['run_id'] = run_id
    (rt/'execution_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'schema_version':'1.0','run_id':run_id,'started_at':now(),'finished_at':None,'input':{'path':str(args.input.resolve()),'sha256':hashlib.sha256(args.input.read_bytes()).hexdigest()},'pipeline_status':'RUNNING','degradation':{'occurred':False,'reasons':[]},'stages':{}}
    safe_write(rt/'run_manifest.json', manifest)
    state={'workflow_status':'AUTONOMOUS_EXECUTION','approved_plan_version':plan['plan_version'],'stages':{},'history':[]}; (rt/'task_state.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    try:
        result=run(rt/'execution_plan.json',rt/'task_state.json',ROOT)
        manifest=safe_load(rt/'run_manifest.json'); manifest['pipeline_status']='PASS'; manifest['finished_at']=now(); safe_write(rt/'run_manifest.json',manifest)
    except Exception:
        manifest=safe_load(rt/'run_manifest.json'); manifest['pipeline_status']='FAILED'; manifest['finished_at']=now(); safe_write(rt/'run_manifest.json',manifest); raise
    print(json.dumps({'status':result['status'],'state':str(rt/'task_state.json')},ensure_ascii=False))
if __name__=='__main__': main()
