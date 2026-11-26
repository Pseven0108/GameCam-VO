"""Recover five VIPER representative native grids without new inference."""
from common import *
from depth_restoration import restore_positive_depth
def main():
    cpu_only();out=ROOT/'02_restoration/source_grid_examples';out.mkdir(exist_ok=False);seen=set();rows=[]
    for row in records():
        item=row['sample']
        if item['dataset']!='VIPER' or item['environment'] in seen:continue
        seen.add(item['environment']);sid=item['sample_id']
        with np.load(row['local_npz'],allow_pickle=False) as a:
            # Explicitly defined two-stage restoration: canonical->tracker input
            # then source grid. No new detail is created by the last enlargement.
            source=restore_positive_depth(a['native_canonical_depth'],row,output_grid='source')
            input_depth=restore_positive_depth(a['native_canonical_depth'],row,output_grid='input')
            expected=np.minimum(resize_bilinear(input_depth,item['source_hw']),300.)
            if not np.allclose(source,expected,rtol=3e-5,atol=3e-4):raise RuntimeError('Source-grid depth unit changed')
            dest=out/(sid+'_source_grid.npz');np.savez_compressed(dest,depth_bilinear_baseline_factor=source.astype('float32'))
            rows.append({'sample_id':sid,'environment':item['environment'],'tracker_input_hw':item['input_hw'],'output_hw':list(source.shape),
                'source_rgb_hw':item['source_hw'],'min_depth':float(source.min()),'depth_unit_multiplied_by_image_resize':False,
                'source_grid_adds_new_geometric_detail':False,'max_abs_vs_resized_input_depth':float(np.max(np.abs(source-expected))),
                'output':str(dest.relative_to(ROOT)),'sha256':sha(dest),'bytes':dest.stat().st_size})
    dump(ROOT/'02_restoration/FULL_SOURCE_GRID_AUDIT.json',{'examples':rows,'five_environments':len(seen),'new_model_forwards':0,
      'notes':'MVS predictions are already restored to native960x540; VIPER R2.1 prediction grid was640x360 with rawRGB1920x1080. Five native1920x1080 maps are included as explicit two-stage exports.'})
    print(json.dumps({'full_source_examples':len(rows),'bytes':sum(x['bytes'] for x in rows)}))
if __name__=='__main__':main()
