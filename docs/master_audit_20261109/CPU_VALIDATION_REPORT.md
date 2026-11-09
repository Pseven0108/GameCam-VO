# CPU validation report

86/86 V2 tests passed: LoaderGate 26, authorization 17, ModelIO 8, DROID-W Supervisor branch 16, config/candidate/environment/startup-order 19. Path contract 12/12, independent CPU subprocess monitoring 13/13, growth guard 11/11 and historical baseline gate 18/18 passed. Real installed API smoke 5/5, RGB decode/hash 120/120 and real upstream CPU dataset 120/120 passed. Native imports under the IO boundary passed without constructing a model, loading a real checkpoint, initializing CUDA or reading GT.

These are CPU engineering results. GPU memory, complete initialization, 120-frame tracking and trajectory accuracy remain unmeasured for this candidate. Failed logs and corrections are preserved. The final candidate is generated outside Git after publication and a fresh clone, avoiding a hash cycle. No new GPU authorization exists.
