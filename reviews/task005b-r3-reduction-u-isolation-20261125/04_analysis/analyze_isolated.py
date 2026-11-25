import itertools,json
from numerics import *
def main():
    rows=[];summary=[];source=[]
    old=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1/expanded/results/trace/trace_reference_1.npz')
    with np.load(old,allow_pickle=False) as z:r2={k:z[k] for k in ['iter1_Jii_data','iter1_Jjj_data','iter1_kf_count','iter1_J_linear']}
    for kind,fields in [('jjj',['Jii_data','Jjj_data','kf_count']),('linear',['J_linear'])]:
        tags=[f'{kind}_{i:02d}' for i in range(1,17)];data={tag:load(tag) for tag in tags}
        for f in fields:
            values=[data[tag][f] for tag in tags]
            pairrows=[]
            for left,right in itertools.combinations(tags,2):
                row={'kind':kind,'field':f,'left':left,'right':right,**compare(data[left][f],data[right][f])};rows.append(row);pairrows.append(row)
            summary.append({'kind':kind,'field':f,**dispersion(values),'pair_count':len(pairrows),'bitwise_equal_pairs':sum(x['bitwise_equal'] for x in pairrows),'tolerance_PASS_pairs':sum(x['PASS'] for x in pairrows),'max_pair_abs':max(x['max_abs'] for x in pairrows),'max_pair_ULP':max(x['max_ULP'] for x in pairrows)})
            a=np.stack(values);spread=np.ptp(a.astype('f8'),axis=0);idx=np.flatnonzero(spread.ravel())
            np.savez_compressed(OUT/(kind+'_'+f+'_ELEMENTWISE_VARIATION.npz'),shape=np.array(a.shape[1:]),variable_flat_indices=idx,min_values=a.reshape(16,-1)[:,idx].min(0),max_values=a.reshape(16,-1)[:,idx].max(0),all_replicate_values=a.reshape(16,-1)[:,idx])
            for tag in tags:source.append({'tag':tag,'field':f,'reference':'R2/trace_reference_1/iter1',**compare(r2['iter1_'+f],data[tag][f])})
    save_csv('ISOLATED_PAIRWISE_ERRORS.csv',rows);save_csv('ISOLATED_SUMMARY.csv',summary);save_csv('ISOLATED_VS_R2_CONTEXT.csv',source)
    save_json('ISOLATED_SUMMARY.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
