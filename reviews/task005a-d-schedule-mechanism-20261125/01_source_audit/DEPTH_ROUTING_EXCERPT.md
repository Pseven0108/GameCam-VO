# 精确源码节选

来源：D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1\raw_evidence\R3_OFFLINE\additional_source_reference\src\depth_video.py

SHA-256：f5686671b168bbc71bbc7079696c96298029cdd891ef7b9c6e48a637df19119d

```text
335: 
336:     def ba(self, target, weight, eta, ii, jj, t0=1, t1=None, iters=2, lm=1e-4, ep=0.1, gamma=0.02, tao=0.1, lr=1e-2, weight_decay=2e-4,
337:            motion_only=False, enable_update_uncer=False, enable_udba=False, visualization_stage=False, *, task004_phase=None):      # ii, jj represent all img pairs
338:         
339:         with self.get_lock():
340:             # [t0, t1] window of bundle adjustment optimization
341:             if t1 is None:
342:                 t1 = max(ii.max().item(), jj.max().item()) + 1
343: 
344:             target = target.view(-1, self.ht//self.down_scale, self.wd//self.down_scale, 2).permute(0,3,1,2).contiguous()
345:             weight = weight.view(-1, self.ht//self.down_scale, self.wd//self.down_scale, 2).permute(0,3,1,2).contiguous()
346: 
347:             # if there is NaN of inf value for self.affine_weights, assert
348:             if self.uncertainty_aware:
349:                 assert not torch.isnan(self.affine_weights).any(), "self.affine_weights has NaN value"
350:                 assert not torch.isinf(self.affine_weights).any(), "self.affine_weights has inf value"
351:             observe = task003()
352:             use_depth, enable_udba, enable_update_uncer = selected_flags(task004_local_flags,
353:                 task004_phase, observe.stage, self, motion_only, enable_update_uncer, enable_udba)
354:             observe.ba_before(self, target, weight, eta, ii, jj, t0, t1, iters, lm, ep, lr, weight_decay,
355:                               motion_only, enable_update_uncer, enable_udba, metric_selected=use_depth,
356:                               local_phase=task004_phase)
357:             if not use_depth:
358:                 droid_backends.ba(self.poses, self.disps, self.intrinsics[0], self.zeros,           # the shape of poses is determined by buffer size
359:                     target, weight, self.uncertainties, 
360:                     self.temp_y_cdot,
361:                     self.dino_feats_resize,
362:                     self.affine_weights,
363:                     eta, ii, jj, t0, t1, iters, lm, ep, 
364:                     self.cfg['tracking']['uncertainty_params']['gamma_data'], 
365:                     self.cfg['tracking']['uncertainty_params']['gamma_prior'], 
366:                     self.cfg['tracking']['uncertainty_params']['gamma_depth'],
367:                     lr, weight_decay,
368:                     motion_only, False, enable_update_uncer,
369:                     enable_udba, self.enable_affine_transform,
370:                     self.enable_bidirectional_uncer,
371:                     self.debug)         # poses: [buffer, 7], disps: [buffer, h, w], 
372:             else:
373:                 droid_backends.ba(self.poses, self.disps, self.intrinsics[0], self.mono_disps,
374:                     target, weight, self.uncertainties, 
375:                     self.temp_y_cdot,
376:                     self.dino_feats_resize,
377:                     self.affine_weights,
378:                     eta, ii, jj, t0, t1, iters, lm, ep, 
379:                     self.cfg['tracking']['uncertainty_params']['gamma_data'], 
380:                     self.cfg['tracking']['uncertainty_params']['gamma_prior'], 
381:                     self.cfg['tracking']['uncertainty_params']['gamma_depth'],
382:                     lr, weight_decay,
383:                     motion_only, False, enable_update_uncer,
384:                     enable_udba, self.enable_affine_transform,
385:                     self.enable_bidirectional_uncer,
386:                     self.debug)          # t0, t1: window of keyframes for BA
387:             
388:             task003().ba_after(self)
389:             self.disps.clamp_(min=1e-5)
390:             task003().ba_after(self, clamped=True)
```
