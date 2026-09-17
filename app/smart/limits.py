"""Apply a Windows per-worker memory limit before parsing untrusted documents."""
import ctypes
from ctypes import wintypes
import os

_jobs=[]


def limit_worker_memory(megabytes=256):
    if os.name!='nt':return
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',wintypes.DWORD),
                  ('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('active',wintypes.DWORD),
                  ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_=[(name,ctypes.c_uint64) for name in ['read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes']]
    class Extended(ctypes.Structure):
        _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                  ('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateJobObjectW;create.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];create.restype=ctypes.c_void_p
    job=create(None,None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    settings=Extended();settings.basic.flags=0x100;settings.process_memory=megabytes*1024*1024
    configure=kernel.SetInformationJobObject;configure.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    assign=kernel.AssignProcessToJobObject;assign.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
    current=kernel.GetCurrentProcess;current.restype=ctypes.c_void_p
    if not configure(job,9,ctypes.byref(settings),ctypes.sizeof(settings)) or not assign(job,current()):
        raise ctypes.WinError(ctypes.get_last_error())
    _jobs.append(job)  # Retain the job handle for the worker process lifetime.
