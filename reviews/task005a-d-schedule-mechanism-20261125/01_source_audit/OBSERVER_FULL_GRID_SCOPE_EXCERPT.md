# 精确源码节选

来源：D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1\raw_evidence\R3_OFFLINE\additional_source_reference\task003_observer.py

SHA-256：1d9173fad166f2563d68a010b8efe98ff326ecf24d54ec4b265a80107a4abea6

```text
298:     def ba_after(self,video,clamped=False):
299:         now = perf_counter_ns()
300:         data = self.before
301:         # Count all active slots at the native return and immediately after Python clamp.
302:         full = self.array(video.disps[:data['n']])
303:         grid = dict(scope='ALL_PIXELS_ACTIVE_SLOT_PREFIX', active_slots=data['n'],
304:                     total=int(full.size), negative=int((np.isfinite(full) & (full < 0)).sum()),
305:                     nonfinite=int((~np.isfinite(full)).sum()),
306:                     float32_floor_count=int((full == np.float32(1e-5)).sum()))
307:         if clamped:
308:             d = full[:,::GRID_STEP,::GRID_STEP]
309:             self.emit('ba_after_clamp',now,ba_id=self.ba_id,disparity=stats(d),full_disparity_grid=grid,
310:                       float32_floor_count=int((d==np.float32(1e-5)).sum()))
311:             self.before = {}
312:         else:
313:             self.emit('ba_after_native',now,ba_id=self.ba_id,rows=self.slots(video,0,data['n']),full_disparity_grid=grid,
314:                       **self.ba_numeric(video,data))
315: 
316:     def filler_begin(self,video,n,m,t0,t1):
317:         now = perf_counter_ns()
```
