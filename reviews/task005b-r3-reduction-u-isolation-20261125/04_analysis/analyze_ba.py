"""Iteration-resolved native/fixed-U and implementation comparisons, no torch."""
import itertools,json,gc
from numerics import *
GROUPS=['original_native','reference_native','paths_native','reference_fixed','paths_fixed']
ORDER=json.loads((ROOT/'02_candidate/TRACE_SCHEMA.json').read_text())
def tags(group):return [f'{group}_{r:02d}' for r in range(1,5)]
def pair(a,b,left,right,comparison):
    fields=[n for n in a if n in b]
    return [{'comparison':comparison,'left':left,'right':right,'field':n,**compare(a[n],b[n])} for n in fields]
def main():
    rows=[];spread=[];summaries=[];chain=[];conditioning=[];control=[]
    for group in GROUPS:
        data={tag:load(tag) for tag in tags(group)}
        endpoint_pass=0
        for left,right in itertools.combinations(data,2):
            a,b=data[left],data[right];pr=pair(a,b,left,right,'within_'+group);rows.extend(pr)
            endpoint_pass+=int(all(x['PASS'] for x in pr if x['field'] in FINAL))
            if group!='original_native':
                it1diff=next((n for n in ORDER if not np.array_equal(a['iter1_'+n],b['iter1_'+n])),None)
                it2diff=next((n for n in ORDER if not np.array_equal(a['iter2_'+n],b['iter2_'+n])),None)
                chain.append({'group':group,'left':left,'right':right,'iter1_first_different_recorded_field':it1diff,'iter2_first_different_recorded_field':it2diff,'iter1_dx_equal':np.array_equal(a['iter1_dx'],b['iter1_dx']),'iter1_dz_equal':np.array_equal(a['iter1_dz'],b['iter1_dz']),'iter2_U_input_equal':np.array_equal(a['iter2_U_before'],b['iter2_U_before']),'iter2_geometry_equal':all(np.array_equal(a['iter2_'+f],b['iter2_'+f]) for f in ['Cii_geometry','wi_geometry','Hs_geometry','vs_geometry']),'iter2_H_rhs_equal':all(np.array_equal(a['iter2_'+f],b['iter2_'+f]) for f in ['H_raw','rhs']),'iter2_dx_equal':np.array_equal(a['iter2_dx'],b['iter2_dx']),'iter2_dz_equal':np.array_equal(a['iter2_dz'],b['iter2_dz'])})
        for f in next(iter(data.values())):spread.append({'group':group,'field':f,**dispersion([a[f] for a in data.values()])})
        summaries.append({'group':group,'calls':4,'within_pair_count':6,'seven_final_fields_PASS_pairs':endpoint_pass,'strict_all_final_pairs_PASS':endpoint_pass==6})
        if group!='original_native':
            for tag,a in data.items():
                for it in (1,2):
                    p=f'iter{it}_';h=a[p+'L_damped_raw'].astype('f8');sym=np.tril(h)+np.tril(h,-1).T
                    eig=np.linalg.eigvalsh(sym);x=a[p+'dx'].astype('f8').ravel();rhs=a[p+'rhs'].ravel()
                    conditioning.append({'tag':tag,'iteration':it,'min_eigenvalue':float(eig[0]),'max_eigenvalue':float(eig[-1]),'condition_number':float(eig[-1]/eig[0]),'SPD':bool(eig[0]>0),'relative_linear_residual':float(np.linalg.norm(sym@x-rhs)/(np.linalg.norm(rhs)+1e-300))})
                    control.append({'tag':tag,'iteration':it,'mode':'fixed' if group.endswith('fixed') else 'native','U_after_equals_call_initial':np.array_equal(a[p+'U_after'],a['iter1_U_before']),'U_computed_equals_U_after':np.array_equal(a[p+'U_computed'],a[p+'U_after']),'U_computed_change_max':compare(a['iter1_U_before'],a[p+'U_computed'])['max_abs'],'affine_actually_updated':not np.array_equal(a[p+'affine_before'],a[p+'affine_after']),'temp_actually_updated':not np.array_equal(a[p+'temp_before'],a[p+'temp_after']),'next_round_feedback_seam_PASS':it==2 or all(np.array_equal(a['iter1_'+f],a['iter2_'+g]) for f,g in [('U_after','U_before'),('temp_after','temp_before'),('affine_after','affine_before'),('poses_after_geometry','poses_before'),('disps_after_geometry','disps_before')])})
        del data;gc.collect()
    cross_summary=[]
    comparisons=[('original_vs_reference_native','original_native','reference_native'),('original_vs_paths_native','original_native','paths_native'),('reference_vs_paths_native','reference_native','paths_native'),('reference_vs_paths_fixed','reference_fixed','paths_fixed'),('reference_native_vs_fixed','reference_native','reference_fixed'),('paths_native_vs_fixed','paths_native','paths_fixed')]
    for label,g1,g2 in comparisons:
        a1={t:load(t) for t in tags(g1)};a2={t:load(t) for t in tags(g2)};passed=0;bitwise=0
        for left,a in a1.items():
            for right,b in a2.items():
                pr=pair(a,b,left,right,label);rows.extend(pr)
                finals=[r for r in pr if r['field'] in FINAL];passed+=all(r['PASS'] for r in finals);bitwise+=all(r['bitwise_equal'] for r in finals)
        cross_summary.append({'comparison':label,'pairs':16,'all_seven_final_PASS_pairs':int(passed),'all_seven_bitwise_equal_pairs':int(bitwise),'all_final_pairs_PASS':passed==16})
        del a1,a2;gc.collect()
    save_csv('BA_PAIRWISE_ERRORS.csv',rows);save_csv('BA_GROUP_DISPERSION.csv',spread);save_csv('BA_REPEATABILITY_SUMMARY.csv',summaries);save_csv('BA_IMPLEMENTATION_COMPARISON.csv',cross_summary);save_csv('BA_FIRST_DIFFERENCE_TIMELINE.csv',chain);save_csv('BA_NORMAL_EQUATION_CONDITIONING.csv',conditioning);save_csv('U_ONLY_CONTROL_VERIFICATION.csv',control)
    # Matched output units: Native versus Fixed variability, never Jjj/dz ratios.
    feedback=[]
    for impl in ('reference','paths'):
        for f in ['iter1_Jjj_data','iter1_J_linear','iter1_U_computed','iter2_U_before','iter2_Cii_geometry','iter2_H_raw','iter2_rhs','iter2_dx','iter2_dz','dx_last','dz_last','poses','disps','affine_weights','temp_y_cdot']:
            a=next(r for r in spread if r['group']==impl+'_native' and r['field']==f);b=next(r for r in spread if r['group']==impl+'_fixed' and r['field']==f)
            feedback.append({'implementation':impl,'field':f,'native_range_max':a['max_range'],'fixed_range_max':b['max_range'],'native_RMS_SD':a['RMS_element_SD'],'fixed_RMS_SD':b['RMS_element_SD'],'native_SD_over_fixed_SD':a['RMS_element_SD']/b['RMS_element_SD'] if b['RMS_element_SD'] else None,'fixed_repeat_bitwise_equal':b['variable_elements']==0})
    save_csv('U_FEEDBACK_VARIABILITY_COMPARISON.csv',feedback)
    result={'within':summaries,'cross':cross_summary,'all_fixed_U_controls_PASS':all(r['U_after_equals_call_initial'] and not r['U_computed_equals_U_after'] for r in control if r['mode']=='fixed'),'all_fixed_affine_and_temp_actually_update':all(r['affine_actually_updated'] and r['temp_actually_updated'] for r in control if r['mode']=='fixed'),'all_feedback_seams_PASS':all(r['next_round_feedback_seam_PASS'] for r in control),'all_systems_SPD':all(r['SPD'] for r in conditioning),'feedback_variability':feedback,'pairwise_rows':len(rows),'n_per_group':4,'paired_comparisons_not_independent_replicates':True}
    save_json('BA_ANALYSIS_SUMMARY.json',result);print(json.dumps({k:v for k,v in result.items() if k!='feedback_variability'},indent=2))
if __name__=='__main__':main()
