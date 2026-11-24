"""Deterministic insertion patch; the original frozen files are never opened for write."""
import ast, difflib, hashlib, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'source_before';CAND=ROOT/'source_candidate'

def edit(name,replacements,append=''):
    p=CAND/name;s=p.read_text(encoding='utf-8')
    for old,new,count in replacements:
        if s.count(old)!=count:raise RuntimeError((name,'patch preimage count',s.count(old),count,old))
        s=s.replace(old,new)
    s+=append
    ast.parse(s,filename=name)
    p.write_text(s,encoding='utf-8',newline='\n')

IMPORT='from native_control.runtime import active as task004c\n'
edit('src/tracker.py',[
 ('from task003_observer import recorder as task003\n',IMPORT+'from task003_observer import recorder as task003\n',1),
 ('        intrinsic = stream.get_intrinsic()\n','        intrinsic = stream.get_intrinsic()\n        native_resume = task004c().tracker_begin(self, stream, dict(next_input_index=0, prev_kf_idx=prev_kf_idx, curr_kf_idx=curr_kf_idx, prev_ba_idx=prev_ba_idx, intrinsic=intrinsic))\n        prev_kf_idx, curr_kf_idx, prev_ba_idx, intrinsic = (native_resume[k] for k in ("prev_kf_idx", "curr_kf_idx", "prev_ba_idx", "intrinsic"))\n',1),
 ('        for i in range(len(stream)):','        for i in range(native_resume["next_input_index"], min(len(stream), 80) if task004c().enabled else len(stream)):',1),
 ('            timestamp, image, _, _ = stream[i]\n','            timestamp, image, _, _ = stream[i]\n            task004c().frame_begin(i, timestamp)\n',1),
 ('            self.printer.update_pbar()\n','            self.printer.update_pbar()\n            task004c().frame_end(self, stream, dict(next_input_index=i+1, prev_kf_idx=prev_kf_idx, curr_kf_idx=curr_kf_idx, prev_ba_idx=prev_ba_idx, intrinsic=intrinsic))\n',1)])
edit('src/motion_filter.py',[
 ('from task003_observer import recorder as task003\n',IMPORT+'from task003_observer import recorder as task003\n',1),
 ('        if self.video.counter.value == 0:\n','        if self.video.counter.value == 0:\n            task004c().motion_decision(True, False, self.thresh)\n',1),
 ('            if delta.norm(dim=-1).mean().item() > self.thresh or force_to_add_keyframe:\n','            native_admit = delta.norm(dim=-1).mean().item() > self.thresh or force_to_add_keyframe\n            native_admit, force_to_add_keyframe = task004c().motion_decision(native_admit, force_to_add_keyframe, self.thresh)\n            if native_admit:\n',1)])
edit('src/frontend.py',[
 ('from task003_observer import recorder as task003\n',IMPORT+'from task003_observer import recorder as task003\n',1),
 ('        if (d.item() < self.keyframe_thresh) & (self.num_keyframes_dropped < self.max_consecutive_drop_of_keyframes) & (not force_to_add_keyframe):\n',
  '        native_drop = (d.item() < self.keyframe_thresh) & (self.num_keyframes_dropped < self.max_consecutive_drop_of_keyframes) & (not force_to_add_keyframe)\n        if task004c().keyframe_decision(native_drop, distance=float(d.item()), threshold=float(self.keyframe_thresh)):\n',1),
 ('        self.graph.age = torch.maximum(self.graph.age-8, torch.tensor(0).to(self.graph.age.device))\n','        self.graph.age = torch.maximum(self.graph.age-8, torch.tensor(0).to(self.graph.age.device))\n        task004c().init_age_reset(self.graph)\n',1)],
 '\nfrom native_control.install import install_frontend\ninstall_frontend(Frontend)\n')
edit('src/factor_graph.py',[
 ('from task003_observer import recorder as task003\n',IMPORT+'from task003_observer import recorder as task003\n',1),
 ('        mask = (torch.abs(self.ii-self.jj) > 2) & (conf < 0.001)\n','        mask = (torch.abs(self.ii-self.jj) > 2) & (conf < 0.001)\n        mask = task004c().bad_edge_mask(self, mask)\n',1),
 ('        if len(es) < 3 or (loop and loop_edges==0):\n','        es, loop_edges = task004c().edge_plan(self, es, loop_edges)\n        if len(es) < 3 or (loop and loop_edges==0):\n',1)],
 '\nfrom native_control.install import install_factor_graph\ninstall_factor_graph(FactorGraph)\n')
edit('src/depth_video.py',[
 ('from task004_controls import local_flags as task004_local_flags\n','from task004_controls import local_flags as task004_local_flags\nfrom native_control.install import selected_flags\n',1),
 ('            use_depth, enable_udba, enable_update_uncer = task004_local_flags(\n','            use_depth, enable_udba, enable_update_uncer = selected_flags(task004_local_flags,\n',1)],
 '\nfrom native_control.install import install_depth_video\ninstall_depth_video(DepthVideo)\n')
edit('src/backend.py',[], '\nfrom native_control.install import install_backend\ninstall_backend(Backend)\n')
edit('src/slam.py',[
 ('from task004_controls import policy as task004_policy\n',IMPORT+'from task004_controls import policy as task004_policy\n',1),
 ('        task003().boundary("final_ba_phase_1", self.video)\n','        task003().boundary("final_ba_phase_1", self.video)\n        task004c().final_phase("begin", stage=1, steps=7, metric_depth_reg=self.video.metric_depth_reg)\n',1),
 ('        task003().boundary("final_phase_1_done", self.video)\n','        task003().boundary("final_phase_1_done", self.video)\n        task004c().final_phase("end", stage=1)\n',1),
 ('            task003().boundary("final_ba_phase_2", self.video)\n','            task003().boundary("final_ba_phase_2", self.video)\n            task004c().final_phase("begin", stage=2, steps=12, metric_depth_reg=self.video.metric_depth_reg)\n',1),
 ('            task003().boundary("final_phase_2_done", self.video)\n','            task003().boundary("final_phase_2_done", self.video)\n            task004c().final_phase("end", stage=2)\n',1),
 ('        exit_event = mp.Event()\n','        exit_event = mp.Event()\n        native_barrier = None\n        if os.environ.get("GAMECAM_NATIVE_CONTROL_BOUNDED") == "1":\n            from native_control.barrier import WriterBarrier\n            native_barrier = WriterBarrier(mp.get_context("spawn"))\n            self.video._native_writer_barrier = native_barrier\n',1),
 ('                    exit_event=exit_event,\n','                    exit_event=exit_event,\n                    writer_barrier=native_barrier,\n',1)])
edit('src/trajectory_filler.py',[
 ('from task003_observer import recorder as task003\n',IMPORT+'from task003_observer import recorder as task003\n',1),
 ('        self.video.counter.value += M\n','        task004c().filler_begin(self.video, N, M, t0, t1, timestamps)\n        self.video.counter.value += M\n',1),
 ('        self.video.counter.value -= M\n','        self.video.counter.value -= M\n        task004c().filler_end(N, M)\n',1)])
edit('src/utils/eval_traj.py',[
 ('from task003_observer import recorder as task003\n',IMPORT+'from task003_observer import recorder as task003\n',1),
 ('    task003().export(traj_est, kf_timestamps)\n','    task003().export(traj_est, kf_timestamps)\n    task004c().export(list(range(1,len(traj_est)+1)), ["KEYFRAME_BA" if i in set(kf_timestamps.tolist()) else "TRAJECTORY_FILLER" for i in range(len(traj_est))])\n',1)])
edit('src/utils/droid_visualization_rerun.py',[
 ('    exit_event=None,\n','    exit_event=None,\n    writer_barrier=None,\n',1),
 ('        while True:\n','        while True:\n            if writer_barrier is not None:\n                writer_barrier.pause_point(torch.cuda.synchronize)\n',1)], '\n_gamecam_original_native_viewer = droid_visualization_rerun\n')

changed=[];lines=[]
for p in sorted(CAND.rglob('*.py')):
    before=BASE/p.relative_to(CAND)
    if not before.is_file():continue
    if before.read_bytes()==p.read_bytes():continue
    a=before.read_text(encoding='utf-8');b=p.read_text(encoding='utf-8')
    if a!=b:
        name=p.relative_to(CAND).as_posix();changed.append(name)
        lines.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
(ROOT/'artifacts/NATIVE_CONTROL_INTERFACE.patch').write_text(''.join(lines),encoding='utf-8')
(ROOT/'evidence/PATCHED_FILES.json').write_text(json.dumps(changed,indent=2))
print(json.dumps({'candidate_files_changed':changed,'original_files_written':0}))
