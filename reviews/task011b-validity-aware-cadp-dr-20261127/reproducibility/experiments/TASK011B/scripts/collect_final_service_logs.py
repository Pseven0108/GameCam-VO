"""Collect all sealed inner-process logs after the serial batch has ended."""
from common import TASK
import collect_native_diagnostics as transfer


def main():
    if not (TASK/'gpu_results/BATCH_COMPLETE.json').exists():
        raise RuntimeError('Do not inventory/hash logs while a formal writer is active')
    r='/root/rivermind-data/'
    transfer.SOURCES={
        'formal_runtime_logs':r+'GAMECAM_TASK011B_20261127_AMP_NATIVE_R2/logs',
        'formal_persistent_job_receipts':r+'GAMECAM_TASK011B_20261127_AMP_NATIVE_R2/job_receipts',
        'FP32_engineering_runtime_logs':r+'GAMECAM_TASK011B_20261127_R1/logs',
    }
    transfer.main()


if __name__=='__main__':main()
