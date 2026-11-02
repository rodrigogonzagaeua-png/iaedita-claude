"""Prazo de uma execução isolada, incluindo todos os seus processos auxiliares."""
from __future__ import annotations

import os
import signal
import subprocess
import time


class _GrupoWindows:
    """Job privado: fechar o handle encerra somente esta árvore, inclusive netos."""
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w

        class Limites(c.Structure):
            _fields_ = [('por_processo', c.c_int64), ('por_grupo', c.c_int64), ('flags', w.DWORD),
                        ('minimo', c.c_size_t), ('maximo', c.c_size_t), ('ativos', w.DWORD),
                        ('afinidade', c.c_size_t), ('prioridade', w.DWORD), ('agendamento', w.DWORD)]

        class IO(c.Structure):
            _fields_ = [(n, c.c_uint64) for n in ('leitura', 'escrita', 'outros', 'bytes_lidos', 'bytes_escritos', 'bytes_outros')]

        class Estendidos(c.Structure):
            _fields_ = [('basicos', Limites), ('io', IO), ('memoria_processo', c.c_size_t),
                        ('memoria_grupo', c.c_size_t), ('pico_processo', c.c_size_t), ('pico_grupo', c.c_size_t)]

        k = self.k = c.WinDLL('kernel32', use_last_error=True)
        k.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.CloseHandle.argtypes = [w.HANDLE]
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise c.WinError(c.get_last_error())
        limites = Estendidos()
        limites.basicos.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle, 9, c.byref(limites), c.sizeof(limites)):
            self.fechar()
            raise c.WinError(c.get_last_error())

    def incluir(self, processo):
        if not self.k.AssignProcessToJobObject(self.handle, int(processo._handle)):
            import ctypes
            raise ctypes.WinError(ctypes.get_last_error())

    def fechar(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None


def executar(comando, prazo_segundos, env=None):
    """O filho espera um byte no stdin antes de criar descendentes.

    Essa barreira garante que a árvore já pertence ao supervisor antes do trabalho.
    stdout/stderr são drenados enquanto o processo roda (sem encher canos).
    """
    inicio = time.monotonic()
    grupo = _GrupoWindows() if os.name == 'nt' else None
    p = None
    expirou = False
    try:
        p = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=env, start_new_session=os.name != 'nt')
        if grupo:
            grupo.incluir(p)
        try:
            saida, _ = p.communicate(b'1', timeout=max(.01, prazo_segundos - (time.monotonic() - inicio)))
        except subprocess.TimeoutExpired:
            expirou = True
            if grupo:
                grupo.fechar()
            else:
                os.killpg(p.pid, signal.SIGKILL)
            saida, _ = p.communicate(timeout=2)
        return {'expirou': expirou, 'codigo': p.returncode, 'saida': saida.decode('utf-8', 'replace')}
    finally:
        if grupo:
            grupo.fechar()
        elif p is not None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if p is not None and p.poll() is None:
            p.kill()
            p.wait(timeout=2)
