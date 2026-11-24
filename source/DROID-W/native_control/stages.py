"""Named stage grants. A larger frame bound requires a different explicit mode."""
from control_common import ControlError

LIMITS={'capture':80,'restore19':19,'short80':80,'formal487':487}
MODES={'capture':('capture',0,None,False),'restore_check':('restore19',0,None,False),
       'record_S1':('short80',1,'S1',False),'replay_D0_S1':('short80',0,'S1',True),
       'record_S0':('short80',0,'S0',False),'replay_D1_S0':('short80',1,'S0',True),
       'B1':('formal487',1,'S1',False),'B2':('formal487',0,'S1',True),
       'B4':('formal487',0,'S0',False),'B3':('formal487',1,'S0',True)}
ORDER=('capture','restore_check','record_S1','replay_D0_S1','record_S0','replay_D1_S0','B1','B2','B4','B3')

def stage_limit(stage):
    if type(stage) is not str or stage not in LIMITS:raise ControlError('Unknown authorized native stage')
    return LIMITS[stage]

def mode_spec(mode,max_rgb=None):
    if mode not in MODES:raise ControlError('Unknown authorized native mode')
    stage,D,schedule,replay=MODES[mode]
    limit=stage_limit(stage)
    if max_rgb is not None and (type(max_rgb) is not int or max_rgb!=limit):
        raise ControlError('Mode/frame authorization mismatch')
    return {'mode':mode,'stage':stage,'max_rgb':limit,'D':D,'W':1,'U':1,'INIT_D':0,
            'schedule':schedule,'replay':replay,'formal':stage=='formal487'}

def schedule_scope(header):
    stage=header.get('stage','short80')
    if stage not in ('short80','formal487') or header.get('max_rgb')!=stage_limit(stage):
        raise ControlError('Schedule stage/frame scope mismatch')
    if any(type(header.get(k)) is not int or header[k]!=v for k,v in [('init_D',0),('W',1),('U',1)]):
        raise ControlError('Schedule D/W/U scope mismatch')
    return stage

def schedule_termination(stage):
    if stage=='short80':return 'PREFIX_RGB080'
    if stage=='formal487':return 'FORMAL_RGB487_NATIVE_COMPLETE'
    raise ControlError('Stage cannot own a schedule')
