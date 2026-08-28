import argparse, json
from pathlib import Path

MODULE_CAPS={
 'channel':['channel_revenue_summary','channel_revenue_rank','channel_cost_summary','channel_roi'],
 'product':['category_revenue_summary','category_revenue_rank','category_revenue_share'],
 'efficiency':['channel_cac','channel_cac_rate','channel_roi'],
 'growth_quality':['channel_roi','period_over_period_change','continuous_trend'],
 'summary':[]}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--preflight',type=Path,required=True); ap.add_argument('--capabilities',type=Path,required=True); ap.add_argument('--facts',type=Path,required=True); ap.add_argument('--rules',type=Path,required=True); ap.add_argument('--output-dir',type=Path,required=True); a=ap.parse_args()
 pre=json.loads(a.preflight.read_text(encoding='utf-8')); caps=json.loads(a.capabilities.read_text(encoding='utf-8'))['capabilities']; facts=json.loads(a.facts.read_text(encoding='utf-8'))['facts']; rules=json.loads(a.rules.read_text(encoding='utf-8')).get('results',[])
 a.output_dir.mkdir(parents=True,exist_ok=True)
 for name, wanted in MODULE_CAPS.items():
  selected=[f for f in facts if not wanted or f['capability_id'] in wanted]
  selected=selected[:120]
  payload={'module':name,'observation':pre.get('discoveries',[{}])[0].get('date_range',{}),'capabilities':[c for c in caps if not wanted or c['capability_id'] in wanted],'facts':selected,'rule_results':[r for r in rules if (name=='summary' or r.get('module','').lower().replace('s','') in {'1' if name=='product' else '2' if name in {'channel','efficiency'} else '3' if name=='growth_quality' else '1'})],'limitations':[c for c in caps if c['status']!='AVAILABLE' and (not wanted or c['capability_id'] in wanted)]}
  (a.output_dir/(name+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
