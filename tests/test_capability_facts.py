import pandas as pd
from src.capability_facts import detect_capabilities, build_facts

def get(c, g): return {x['capability_id']: x for x in detect_capabilities(c, g)}

def test_rules_zero_still_has_current_facts():
    c=pd.DataFrame({'month':['2025-01'],'channel':['A'],'is_complete_month':[False],'first_order_revenue':[100],'cost':[50],'first_order_orders':[2],'first_order_net_revenue':[80]})
    g=pd.DataFrame({'month':['2025-01'],'category':['X'],'is_complete_month':[False],'category_revenue':[100],'revenue_share':[1.0]})
    x=get(c,g); assert x['channel_revenue_summary']['status']=='AVAILABLE'; assert x['period_over_period_change']['status']=='UNAVAILABLE'
    assert build_facts(c,g,list(x.values()),{'channel':'channel_metrics.csv','category':'category_metrics.csv'})

def test_missing_cost_disables_cost_dependent_capabilities():
    c=pd.DataFrame({'month':['2025-01'],'channel':['A'],'is_complete_month':[False],'first_order_revenue':[100]})
    x=get(c,pd.DataFrame()); assert x['channel_revenue_summary']['status']=='AVAILABLE'; assert x['channel_roi']['status']=='UNAVAILABLE'; assert x['channel_cac']['status']=='UNAVAILABLE'

def test_missing_category_does_not_disable_channel():
    c=pd.DataFrame({'month':['2025-01'],'channel':['A'],'is_complete_month':[False],'first_order_revenue':[100]})
    x=get(c,pd.DataFrame()); assert x['channel_revenue_rank']['status']=='AVAILABLE'; assert x['category_revenue_summary']['status']=='UNAVAILABLE'

def test_complete_periods_enable_cross_period_capabilities():
    c=pd.DataFrame({'month':['2025-01','2025-02','2025-03'],'channel':['A']*3,'is_complete_month':[True]*3,'first_order_revenue':[1,2,3],'cost':[1,1,1],'first_order_orders':[1,1,1],'first_order_net_revenue':[1,1,1]})
    x=get(c,pd.DataFrame()); assert x['period_over_period_change']['status']=='AVAILABLE'; assert x['continuous_trend']['status']=='AVAILABLE'
