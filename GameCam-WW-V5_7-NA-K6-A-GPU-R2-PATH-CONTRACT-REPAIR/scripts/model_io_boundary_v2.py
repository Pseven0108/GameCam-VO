"""Audited Python file boundary; this is not an OS or native-code sandbox.

The worker boundary deliberately separates model output, worker telemetry, and
supervisor-controlled session files.  A native extension or an already-open
file descriptor is outside this Python audit-hook boundary.
"""
import errno
import os
import pathlib
import re
import stat
import sys


class ModelIOBoundary:
    def __init__(
        self,
        read_files,
        source_files,
        protected_roots,
        output_roots,
        environment_roots=(),
        ipc_policy=None,
        worker_files=(),
        worker_read_files=(),
        worker_atomic_files=(),
        worker_root=None,
        import_scratch_root=None,
    ):
        self.reads = {pathlib.Path(p).resolve() for p in list(read_files) + list(source_files)}
        self.protected = [pathlib.Path(p).resolve() for p in protected_roots]
        self.outputs = [pathlib.Path(p).resolve() for p in output_roots]
        self.environments = [pathlib.Path(p).resolve() for p in environment_roots]
        self.worker_files = {pathlib.Path(p).absolute() for p in worker_files}
        self.worker_read_files = {pathlib.Path(p).absolute() for p in worker_read_files}
        self.worker_atomic_files = {pathlib.Path(p).absolute() for p in worker_atomic_files}
        if worker_root is None and (self.worker_files or self.worker_read_files):
            parents = [str(p.parent) for p in self.worker_files | self.worker_read_files]
            worker_root = pathlib.Path(os.path.commonpath(parents)) if parents else None
        self.worker_root = pathlib.Path(worker_root).resolve() if worker_root is not None else None
        self.import_scratch_root = pathlib.Path(import_scratch_root).absolute() if import_scratch_root else None
        if self.import_scratch_root is not None:
            if not any(self.import_scratch_root == r / 'import_tmp' for r in self.outputs) or self.import_scratch_root.resolve() != self.import_scratch_root:
                raise RuntimeError('MODEL_IMPORT_SCRATCH_IDENTITY')
        self.ipc = ipc_policy
        self.events = []
        if any(str(p) in ('/', '/dev/shm', '/dev/shm/gamecam-ipc', '/tmp') for p in self.outputs):
            raise RuntimeError('MODEL_BROAD_OUTPUT_ROOT_FORBIDDEN')
        if self.worker_root is not None and not self.worker_root.is_absolute():
            raise RuntimeError('MODEL_WORKER_ROOT_NOT_ABSOLUTE')
        if self.worker_root is not None:
            if any(self.worker_root.is_relative_to(root) for root in self.outputs):
                raise RuntimeError('MODEL_SESSION_ROOT_AS_OUTPUT_FORBIDDEN')
            for p in self.worker_files | self.worker_read_files | self.worker_atomic_files:
                if not p.is_relative_to(self.worker_root):
                    raise RuntimeError('MODEL_WORKER_FILE_OUTSIDE_ROOT:' + str(p))

    def _worker_temp_target(self, lexical):
        if self.worker_root is None or not lexical.is_relative_to(self.worker_root):
            return None
        suffix = '.' + str(os.getpid()) + '.tmp'
        for target in self.worker_files:
            if lexical.parent == target.parent and lexical.name == target.name + suffix:
                return target
        return None

    @staticmethod
    def _flags_from_open_args(mode, flags):
        # The audit event for os.open uses integer flags as its mode argument
        # on some Python builds, while builtins.open supplies a string mode.
        if isinstance(mode, int) and (flags is None or flags == 0):
            return mode, None
        return flags if isinstance(flags, int) else 0, mode

    def _worker_check(self, lexical, write, operation='open', flags=None, mode=None):
        resolved = lexical.resolve(strict=False)
        if resolved != lexical:
            raise RuntimeError('MODEL_SESSION_SYMLINK_ESCAPE:' + str(lexical))
        if lexical.exists():
            info = lexical.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise RuntimeError('MODEL_SESSION_FILE_IDENTITY:' + str(lexical))
        if not lexical.is_relative_to(self.worker_root):
            raise RuntimeError('MODEL_WORKER_PATH_OUTSIDE_ROOT:' + str(lexical))
        if not write:
            if lexical in self.worker_read_files or lexical in self.worker_files:
                return True
            raise RuntimeError('MODEL_SESSION_READ_OUTSIDE_ALLOWLIST:' + str(lexical))

        temp_target = self._worker_temp_target(lexical)
        if temp_target is not None:
            if temp_target not in self.worker_atomic_files:
                raise RuntimeError('MODEL_WORKER_APPEND_FILE_ATOMIC_REPLACE_FORBIDDEN:' + str(lexical))
            if operation == 'open':
                open_flags, open_mode = self._flags_from_open_args(mode, flags)
                if isinstance(open_mode, str):
                    if not (open_flags & os.O_CREAT and open_flags & os.O_EXCL) or open_mode not in ('w', 'wb', 'x', 'xb'):
                        raise RuntimeError('MODEL_WORKER_TEMP_MODE_FORBIDDEN:' + str(lexical))
                elif not (
                    open_flags & os.O_CREAT
                    and open_flags & os.O_EXCL
                    and open_flags & (os.O_WRONLY | os.O_RDWR)
                    and not open_flags & os.O_TRUNC
                ):
                    raise RuntimeError('MODEL_WORKER_TEMP_OPEN_FORBIDDEN:' + str(lexical))
            elif operation not in ('rename_source', 'os.remove'):
                raise RuntimeError('MODEL_WORKER_TEMP_OPERATION_FORBIDDEN:' + str(lexical))
            return True

        if lexical in self.worker_files:
            if lexical in self.worker_atomic_files and operation == 'open':
                raise RuntimeError('MODEL_WORKER_ATOMIC_DIRECT_OPEN_FORBIDDEN:' + str(lexical))
            if operation == 'open':
                open_flags, open_mode = self._flags_from_open_args(mode, flags)
                if isinstance(open_mode, str):
                    if open_mode not in ('a', 'ab'):
                        raise RuntimeError('MODEL_WORKER_DIRECT_OVERWRITE_FORBIDDEN:' + str(lexical))
                elif not (
                    open_flags & os.O_APPEND
                    and open_flags & (os.O_WRONLY | os.O_RDWR)
                    and not open_flags & os.O_TRUNC
                ):
                    raise RuntimeError('MODEL_WORKER_DIRECT_OPEN_FORBIDDEN:' + str(lexical))
                return True
            if operation == 'rename_destination':
                return True
            raise RuntimeError('MODEL_WORKER_CONTROL_FILE_MUTATION_FORBIDDEN:' + str(lexical))

        raise RuntimeError('MODEL_SESSION_WRITE_OUTSIDE_ALLOWLIST:' + str(lexical))

    def check_path(self, path, write=False, operation='open', flags=None, mode=None):
        if write and not pathlib.Path(path).is_absolute():
            raise RuntimeError('MODEL_RELATIVE_WRITE_FORBIDDEN:' + str(path))
        lexical = pathlib.Path(os.path.abspath(path))
        p = lexical.resolve(strict=False)
        if self.ipc is not None and (self.ipc.is_ipc_path(lexical) or self.ipc.is_ipc_path(p)):
            return self.ipc.check_file(lexical, write, operation, flags)
        in_output = any(lexical.is_relative_to(r) and p.is_relative_to(r) for r in self.outputs)
        if in_output:
            if write and lexical != p:
                raise RuntimeError('MODEL_OUTPUT_SYMLINK_FORBIDDEN:' + str(lexical))
            if write and lexical.exists() and lexical.is_file() and lexical.stat().st_nlink != 1:
                raise RuntimeError('MODEL_OUTPUT_HARDLINK_FORBIDDEN:' + str(lexical))
            return True
        if self.worker_root is not None and (lexical.is_relative_to(self.worker_root) or p.is_relative_to(self.worker_root)):
            if lexical != p:
                raise RuntimeError('MODEL_SESSION_SYMLINK_ESCAPE:' + str(lexical))
            return self._worker_check(lexical, write, operation, flags, mode)
        if write:
            raise RuntimeError('MODEL_WRITE_OUTSIDE_OWN_OUTPUT:' + str(p))
        if p in self.reads:
            return True
        if any(p.is_relative_to(r) for r in self.protected):
            raise RuntimeError('MODEL_UNAPPROVED_PROJECT_READ:' + str(p))
        if any(p.is_relative_to(r) for r in self.environments) and p.suffix.lower() in {'.py', '.pyc', '.so', '.pyd', '.dll'}:
            return True
        if re.search(r'(?i)(^|[_-])(gt|skeleton|state|npc|monster|camera_pose|ground_truth)([_\-.]|$)', p.name):
            raise RuntimeError('MODEL_ANALYSIS_DATA_FORBIDDEN:' + str(p))
        if any(p.is_relative_to(r) for r in self.environments):
            return True
        if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.exr', '.npy', '.npz', '.pt', '.pth', '.safetensors', '.csv', '.mp4'}:
            raise RuntimeError('MODEL_UNAPPROVED_EXTERNAL_DATA_READ:' + str(p))
        return True

    def _in_import_scratch(self, path):
        p = pathlib.Path(os.path.abspath(path))
        return self.import_scratch_root is not None and p.is_relative_to(self.import_scratch_root) and p.resolve(strict=False) == p

    def _check_import_scratch_dirfd_delete(self, event, args, dirfd):
        if event not in {'os.remove', 'os.rmdir'} or not isinstance(args[0], (str, bytes, os.PathLike)):
            return False
        name = os.fsdecode(args[0])
        if name in {'', '.', '..'} or pathlib.Path(name).name != name:
            return False
        try:
            base = pathlib.Path(os.readlink('/proc/self/fd/' + str(dirfd)))
            if not self._in_import_scratch(base):
                return False
            opened = os.fstat(dirfd); current = base.stat()
            if not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.getuid() or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                return False
            target = base / name
            if not self._in_import_scratch(target):
                return False
            self.check_path(target, True, event)
            return True
        except OSError:
            return False

    def audit(self, event, args):
        try:
            dirfd_indices = {'os.mkdir': (2,), 'os.remove': (1,), 'os.rmdir': (1,), 'os.chmod': (2,), 'os.chown': (3,), 'os.rename': (2, 3)}
            for index in dirfd_indices.get(event, ()):
                if len(args) > index and args[index] not in (None, -1):
                    if self._check_import_scratch_dirfd_delete(event, args, args[index]):
                        return
                    raise RuntimeError('MODEL_DIR_FD_OPERATION_FORBIDDEN')
            if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
                mode = args[1] if len(args) > 1 else None
                flags = args[2] if len(args) > 2 else 0
                open_flags, open_mode = self._flags_from_open_args(mode, flags)
                write = (
                    isinstance(open_mode, str) and any(c in open_mode for c in 'wax+')
                ) or (
                    isinstance(open_flags, int) and bool(open_flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                )
                self.check_path(os.fsdecode(args[0]), write, 'open', open_flags, open_mode)
            elif event in {'os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.chown'} and args and isinstance(args[0], (str, bytes, os.PathLike)):
                path = os.fsdecode(args[0])
                self.check_path(path, True, event)
                if self.ipc is not None and self.ipc.is_ipc_path(path) and event == 'os.remove':
                    self.ipc.file_unlinked(path)
            elif event == 'os.rename':
                source = pathlib.Path(os.path.abspath(os.fsdecode(args[0])))
                destination = pathlib.Path(os.path.abspath(os.fsdecode(args[1])))
                temp_target = self._worker_temp_target(source)
                if destination in self.worker_files and temp_target != destination:
                    raise RuntimeError('MODEL_WORKER_ATOMIC_SOURCE_FORBIDDEN:' + str(source))
                if temp_target is not None:
                    if destination != temp_target:
                        raise RuntimeError('MODEL_WORKER_TEMP_RENAME_ESCAPE:' + str(destination))
                    self.check_path(source, True, 'rename_source')
                    self.check_path(destination, True, 'rename_destination')
                else:
                    self.check_path(source, True, 'rename_source')
                    self.check_path(destination, True, 'rename_destination')
            elif event == 'os.link':
                if len(args) >= 2 and all(isinstance(p, (str, bytes, os.PathLike)) and self._in_import_scratch(p) for p in args[:2]):
                    raise PermissionError(errno.EPERM, 'MODEL_HARD_LINK_FORBIDDEN_IN_IMPORT_SCRATCH')
                raise RuntimeError('MODEL_HARD_LINK_FORBIDDEN')
            elif event == 'os.symlink':
                raise RuntimeError('MODEL_SYMLINK_FORBIDDEN')
            elif event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
                self.events.append({'event': 'network_denied'})
                raise RuntimeError('MODEL_NETWORK_FORBIDDEN')
        except RuntimeError as exc:
            self.events.append({
                'event': 'denied_open' if event == 'open' else 'denied_filesystem_operation',
                'audit_event': event,
                'reason': str(exc),
            })
            raise

    def install(self):
        sys.addaudithook(self.audit)
