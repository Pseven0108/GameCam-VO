"""Summarize recorded endpoints and CPU source-formula U weight proxies, no GPU."""
import collections,itertools
from numerics import *

def main():
    with (OUT/'BA_PAIRWISE_ERRORS.csv').open(encoding='utf-8-sig',newline='') as f:
        pairs=list(csv.DictReader(f))
    buckets=collections.defaultdict(list)
    for row in pairs:
        if row['field'] in FINAL:
            buckets[row['comparison'],row['field']].append(row)
    summaries=[]
    for (comparison,field),r in buckets.items():
        summaries.append({'comparison':comparison,'field':field,'related_pairs':len(r),
                          'PASS_pairs':sum(x['PASS']=='True' for x in r),
                          'bitwise_equal_pairs':sum(x['bitwise_equal']=='True' for x in r),
                          'max_pair_abs':max(float(x['max_abs']) for x in r),
                          'max_violations_in_one_pair':max(int(x['violations']) for x in r)})
    save_csv('BA_FINAL_FIELD_COMPARISON_SUMMARY.csv',summaries)

    stats=[];variation=[]
    for group in ['reference_native','paths_native','reference_fixed','paths_fixed']:
        stage_values={1:[],2:[]}
        for rep in range(1,5):
            tag=f'{group}_{rep:02d}'
            with np.load(DATA/(tag+'.npz'),allow_pickle=False) as a:
                for it in (1,2):
                    kx=a[f'iter{it}_kx'];U=a[f'iter{it}_U_before'][kx].astype('f8')
                    # Formula proxy only: not a bitwise CUDA/FMA or validity-mask reconstruction.
                    w=np.clip(1./np.maximum(45.*U-35.,.1),0.,1.)
                    assert np.isfinite(w).all()
                    stage_values[it].append(w)
                    stats.append({'tag':tag,'iteration':it,'active_depth_slots':len(kx),
                                  'slot_pixel_count':int(w.size),'min':float(w.min()),
                                  'median':float(np.median(w)),'P95':float(np.quantile(w,.95)),
                                  'max':float(w.max()),'unit_weight_pixels':int(np.count_nonzero(w==1.)),
                                  'source':'CPU_FP64_formula_on_recorded_U_before_not_native_weight_dump'})
        for it,values in stage_values.items():
            variation.append({'group':group,'iteration':it,**dispersion(values)})
    save_csv('U_GEOMETRY_WEIGHT_PROXY_STATISTICS.csv',stats)
    save_csv('U_GEOMETRY_WEIGHT_PROXY_REPEATABILITY.csv',variation)
    fixed_second=all(r['variable_elements']==0 for r in variation if r['group'].endswith('fixed') and r['iteration']==2)
    native_second=all(r['variable_elements']>0 for r in variation if r['group'].endswith('native') and r['iteration']==2)
    text='''# U 到几何权重的源码公式核查

真实 GPU 记录包括 U_before、几何 Cii/wi/Hs/vs、Schur 系统和 dx/dz。本补充不新增 GPU 计算，从已保存的 U_before 按源码公式计算 CPU FP64 权重代理：

`w_U = clip(1 / max(45 U - 35, 0.1), 0, 1)`。

本状态 enable_udba=true、enable_bidirectional_uncer=false。原 kernel 将源端权重乘到 `.001 * graph_weight`，另受投影深度有效性控制。这里统计 kx 唯一深度槽位像素，未按图边重复，也不声称已经捕获全部有效边的最终权重。FP64 公式不模拟 CUDA 的浮点舍入、FMA 或有效性掩码，不能作为 native 权重的逐位证书。

逐调用分布见 U_GEOMETRY_WEIGHT_PROXY_STATISTICS.csv；重复离散度见 U_GEOMETRY_WEIGHT_PROXY_REPEATABILITY.csv。

'''
    text+=f'Fixed U 第二轮代理在各实现内部逐位重复：{fixed_second}。Native U 第二轮代理在两个实现中都存在变化：{native_second}。几何方程与解的真实 GPU 变化另见 BA_GROUP_DISPERSION.csv，不能用本代理替代。\n\n'
    text+='最终七字段分项通过数、逐位相同数、最大绝对差及单个配对最多超差元素见 BA_FINAL_FIELD_COMPARISON_SUMMARY.csv。所有配对共享调用，不能视为独立样本。\n'
    (ROOT/'R3_GEOMETRY_WEIGHT_AUDIT.md').write_text(text,encoding='utf-8')
    print(json.dumps({'final_field_summary_rows':len(summaries),'weight_statistic_rows':len(stats),'weight_variability_rows':len(variation),'fixed_second_repeat':fixed_second,'native_second_varies':native_second},indent=2))

if __name__=='__main__':main()
